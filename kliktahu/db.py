"""kliktahu/db.py - basis data lokal SQLite (WAL, foreign key, FTS5) + LAPISAN AKSES DATA (DAL).

* Skema dari kliktahu/skema.py (satu sumber). Migrasi berurutan lewat PRAGMA user_version.
* Aturan keras §2.6 ditegakkan di DAL: topik/frasa DIBLOKIR ditolak & dibuang dari data sebelum disimpan.
* Berkas DB (data/kliktahu.db) diabaikan git; data tahan-lama = ekspor JSONL di data/ekspor/ (di-commit,
  bisa di-diff, dipulihkan dengan `python3 -m kliktahu db impor`). Sandbox bisa reset -> ekspor tiap run.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from . import ROOT, skema, teks
from . import kanal as kanal_mod

DB_BAWAAN = ROOT / "data" / "kliktahu.db"
EKSPOR_DIR = ROOT / "data" / "ekspor"
WIB = dt.timezone(dt.timedelta(hours=7), "WIB")
MIGRASI = {1: skema.ddl_sqlite}
TANPA_EKSPOR = {"snapshot_pencarian"}  # besar & bisa diambil ulang; sinyal ringkas ada di tabel skor


def sekarang() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def hari_ini_wib() -> dt.date:
    return dt.datetime.now(WIB).date()


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class DataDiblokir(ValueError):
    """upaya menyimpan topik/frasa yang diblokir pemilik."""


class DB:
    def __init__(self, path: Path | str | None = None, kanal: kanal_mod.Kanal | None = None) -> None:
        self.path = str(path or DB_BAWAAN)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.kanal = kanal or kanal_mod.muat()
        self.con = sqlite3.connect(self.path, timeout=30)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("PRAGMA busy_timeout = 30000")
        if self.path != ":memory:":
            self.con.execute("PRAGMA journal_mode = WAL")
        self._migrasi()

    # ------------------------------------------------------------------------------------ infrastruktur
    def _migrasi(self) -> None:
        v = self.con.execute("PRAGMA user_version").fetchone()[0]
        for n in sorted(MIGRASI):
            if n > v:
                self.con.executescript(MIGRASI[n]())
                self.con.execute(f"PRAGMA user_version = {n}")
        self.con.commit()

    @property
    def versi(self) -> int:
        return int(self.con.execute("PRAGMA user_version").fetchone()[0])

    def tutup(self) -> None:
        self.con.close()

    def __enter__(self) -> DB:
        return self

    def __exit__(self, *a: object) -> None:
        self.con.commit()
        self.tutup()

    def _enc(self, tabel: str, data: dict[str, Any]) -> dict[str, Any]:
        t = skema.T[tabel]
        nama = {c.nama for c in t.kolom}
        out: dict[str, Any] = {}
        for k, v in data.items():
            if k not in nama:
                raise KeyError(f"kolom '{k}' tidak ada di tabel {tabel}")
            c = t.k(k)
            if v is None:
                out[k] = None
            elif c.tipe == "json":
                out[k] = _json(v)
            elif c.tipe == "bool":
                out[k] = 1 if v else 0
            elif c.tipe in ("waktu", "tanggal") and isinstance(v, (dt.date, dt.datetime)):
                out[k] = v.isoformat()
            else:
                out[k] = v
        return out

    def _dec(self, tabel: str, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        t = skema.T[tabel]
        d = dict(row)
        for c in t.kolom:
            if c.nama in d and d[c.nama] is not None:
                if c.tipe == "json":
                    d[c.nama] = json.loads(d[c.nama])
                elif c.tipe == "bool":
                    d[c.nama] = bool(d[c.nama])
        return d

    def sisip(self, tabel: str, data: dict[str, Any]) -> int:
        e = self._enc(tabel, data)
        kol = ", ".join(e)
        cur = self.con.execute(f"INSERT INTO {tabel} ({kol}) VALUES ({', '.join('?' * len(e))})", tuple(e.values()))
        return int(cur.lastrowid or 0)

    def upsert(self, tabel: str, data: dict[str, Any], kunci: Sequence[str]) -> int:
        e = self._enc(tabel, data)
        if "diubah" in {c.nama for c in skema.T[tabel].kolom} and "diubah" not in e:
            e["diubah"] = sekarang()
        kol = ", ".join(e)
        set_ = (
            ", ".join(f"{k} = excluded.{k}" for k in e if k not in kunci and k != "dibuat")
            or f"{kunci[0]} = excluded.{kunci[0]}"
        )
        sql = (
            f"INSERT INTO {tabel} ({kol}) VALUES ({', '.join('?' * len(e))}) "
            f"ON CONFLICT ({', '.join(kunci)}) DO UPDATE SET {set_} RETURNING id"
        )
        return int(self.con.execute(sql, tuple(e.values())).fetchone()[0])

    def ambil(self, tabel: str, **where: Any) -> dict[str, Any] | None:
        e = self._enc(tabel, where)
        syarat = " AND ".join(f"{k} IS ?" for k in e) or "1"
        return self._dec(
            tabel, self.con.execute(f"SELECT * FROM {tabel} WHERE {syarat} LIMIT 1", tuple(e.values())).fetchone()
        )

    def daftar(
        self, tabel: str, where: str = "", params: Sequence[Any] = (), urut: str = "id", batas: int | None = None
    ) -> list[dict[str, Any]]:
        sql = f"SELECT * FROM {tabel}" + (f" WHERE {where}" if where else "") + f" ORDER BY {urut}"
        if batas:
            sql += f" LIMIT {int(batas)}"
        return [self._dec(tabel, r) for r in self.con.execute(sql, tuple(params)).fetchall()]  # type: ignore[misc]

    def ubah(self, tabel: str, id_: int, **fields: Any) -> None:
        if "diubah" in {c.nama for c in skema.T[tabel].kolom}:
            fields.setdefault("diubah", sekarang())
        e = self._enc(tabel, fields)
        self.con.execute(f"UPDATE {tabel} SET {', '.join(f'{k} = ?' for k in e)} WHERE id = ?", (*e.values(), id_))

    def hitung(self, tabel: str, where: str = "", params: Sequence[Any] = ()) -> int:
        return int(
            self.con.execute(
                f"SELECT COUNT(*) FROM {tabel}" + (f" WHERE {where}" if where else ""), tuple(params)
            ).fetchone()[0]
        )

    def commit(self) -> None:
        self.con.commit()

    # ------------------------------------------------------------------------------------ blokir
    def _blokir(self) -> tuple[str, ...]:
        return self.kanal.aturan.blokir

    def saring(self, obj: Any) -> Any:
        """buang isi terblokir secara rekursif. Rekaman (dict) yang memuat teks terblokir dibuang utuh."""
        b = self._blokir()
        if isinstance(obj, str):
            return None if teks.diblokir(obj, b) else obj
        if isinstance(obj, list):
            out = [self.saring(x) for x in obj]
            return [x for x in out if x is not None]
        if isinstance(obj, dict):
            if any(isinstance(v, str) and teks.diblokir(v, b) for v in obj.values()):
                return None
            return {k: self.saring(v) for k, v in obj.items() if not teks.diblokir(str(k), b)}
        return obj

    # ------------------------------------------------------------------------------------ topik
    def upsert_topik(
        self, slug: str, nama: str, pilar: str, kata_kunci: Sequence[str] = (), aspek: Sequence[str] = (), **lain: Any
    ) -> int:
        if teks.diblokir(nama, self._blokir()) or teks.diblokir(slug.replace("_", " "), self._blokir()):
            raise DataDiblokir(f"topik '{nama}' DIBLOKIR pemilik (aturan keras §2.6) - tidak disimpan")
        data = {
            "slug": slug,
            "nama": nama,
            "pilar": pilar,
            "kata_kunci": teks.buang_blokir(kata_kunci, self._blokir()),
            "aspek": teks.buang_blokir(aspek, self._blokir()),
            **lain,
        }
        return self.upsert("topik", data, ("slug",))

    def seed_tema(self) -> int:
        from .tema import DAFTAR

        n = 0
        for t in DAFTAR:
            ada = self.ambil("topik", slug=teks.slug(t.nama))
            lain: dict[str, Any] = {"nama_en": t.en, "wiki": t.wiki, "evergreen": bool(t.ever), "visual": t.visb}
            if ada is None:
                n += 1
            self.upsert_topik(teks.slug(t.nama), t.nama, t.pilar, t.kata, t.aspek, **lain)
        self.commit()
        return n

    def topik(self, slug_atau_nama: str) -> dict[str, Any] | None:
        return self.ambil("topik", slug=teks.slug(slug_atau_nama)) or self.ambil("topik", nama=slug_atau_nama)

    def daftar_topik(self, status: str | None = None, pilar: str | None = None) -> list[dict[str, Any]]:
        syarat, par = [], []
        if status:
            syarat.append("status = ?")
            par.append(status)
        if pilar:
            syarat.append("pilar = ?")
            par.append(pilar)
        return self.daftar("topik", " AND ".join(syarat), par, urut="nama")

    # ------------------------------------------------------------------------------------ episode
    def kode_berikut(self, format_: str) -> str:
        pre, awal = ("Ep", self.kanal.shorts_terakhir) if format_ == "shorts" else ("Long", self.kanal.long_terakhir)
        n = awal
        for r in self.con.execute("SELECT kode FROM episode WHERE format = ?", (format_,)):
            s = r[0][len(pre) :]
            if r[0].startswith(pre) and s.isdigit():
                n = max(n, int(s))
        return f"{pre}{n + 1:02d}"

    def tambah_episode(self, format_: str, topik_slug: str | None = None, kode: str | None = None, **lain: Any) -> str:
        kode = kode or self.kode_berikut(format_)
        tid = None
        if topik_slug:
            t = self.topik(topik_slug)
            if t is None:
                raise KeyError(f"topik '{topik_slug}' belum ada di basis data")
            tid = t["id"]
        self.sisip("episode", {"kode": kode, "format": format_, "topik_id": tid, **lain})
        self.commit()
        return kode

    def episode(self, kode: str) -> dict[str, Any] | None:
        return self.ambil("episode", kode=kode)

    def ubah_episode(self, kode: str, **fields: Any) -> None:
        e = self.episode(kode)
        if e is None:
            raise KeyError(f"episode {kode} tidak ada")
        self.ubah("episode", e["id"], **fields)
        if fields.get("status") == "rilis" and e.get("topik_id"):
            self.ubah("topik", e["topik_id"], status="dibahas" if e["format"] == "shorts" else "long")
        self.commit()

    # ------------------------------------------------------------------------------------ metadata
    def simpan_metadata(self, m: dict[str, Any]) -> int:
        bersih = self.saring(m)
        if bersih is None or any(teks.diblokir(j, self._blokir()) for j in m.get("judul", [])):
            raise DataDiblokir("metadata memuat topik diblokir - tidak disimpan")
        v = self.con.execute(
            "SELECT COALESCE(MAX(versi), 0) FROM metadata WHERE topik_id IS ? AND episode_id IS ?",
            (m.get("topik_id"), m.get("episode_id")),
        ).fetchone()[0]
        return self.sisip("metadata", {**bersih, "versi": int(v) + 1})

    def metadata_terbaru(self, topik_id: int | None = None, episode_id: int | None = None) -> dict[str, Any] | None:
        r = self.con.execute(
            "SELECT * FROM metadata WHERE topik_id IS ? AND episode_id IS ? ORDER BY versi DESC LIMIT 1",
            (topik_id, episode_id),
        ).fetchone()
        return self._dec("metadata", r)

    # ------------------------------------------------------------------------------------ run & snapshot
    def mulai_run(self, mode: str, tanggal: dt.date | None = None, versi: str = "") -> int:
        from . import __version__

        rid = self.sisip(
            "run_riset",
            {"mode": mode, "versi": versi or __version__, "tanggal": (tanggal or hari_ini_wib()).isoformat()},
        )
        self.commit()
        return rid

    def selesai_run(self, run_id: int, statistik: dict[str, Any], catatan: str | None = None) -> None:
        self.ubah("run_riset", run_id, selesai=sekarang(), statistik=statistik, catatan=catatan)
        self.commit()

    def run_terakhir(
        self,
        sebelum_id: int | None = None,
        mode: Iterable[str] = ("online", "agen", "manual"),
        tanggal_sebelum: str | None = None,
    ) -> dict[str, Any] | None:
        mode = tuple(mode)
        syarat = [f"mode IN ({', '.join('?' * len(mode))})", "selesai IS NOT NULL"]
        par: list[Any] = list(mode)
        if sebelum_id is not None:
            syarat.append("id < ?")
            par.append(sebelum_id)
        if tanggal_sebelum:
            syarat.append("tanggal < ?")
            par.append(tanggal_sebelum)
        r = self.daftar("run_riset", " AND ".join(syarat), par, urut="id DESC", batas=1)
        return r[0] if r else None

    def simpan_snapshot(
        self,
        run_id: int | None,
        sumber: str,
        kueri: str,
        data: Any,
        status: int = 0,
        durasi_ms: int = 0,
        dari_cache: bool = False,
        topik_id: int | None = None,
    ) -> int | None:
        if teks.diblokir(kueri, self._blokir()):
            return None
        bersih = self.saring(data)
        if bersih is None:
            return None
        jml = (
            len(bersih)
            if isinstance(bersih, list)
            else len(bersih.get("items", []))
            if isinstance(bersih, dict) and isinstance(bersih.get("items"), list)
            else 1
        )
        sidik = hashlib.sha1(_json(bersih).encode()).hexdigest()
        return self.sisip(
            "snapshot_pencarian",
            {
                "run_id": run_id,
                "sumber": sumber,
                "kueri": kueri,
                "topik_id": topik_id,
                "status": status,
                "durasi_ms": durasi_ms,
                "dari_cache": dari_cache,
                "jumlah": jml,
                "data": bersih,
                "sidik": sidik,
            },
        )

    # ------------------------------------------------------------------------------------ skor
    def simpan_skor(self, run_id: int, rows: Sequence[dict[str, Any]]) -> None:
        for r in rows:
            self.upsert("skor", {**r, "run_id": run_id}, ("run_id", "topik_id"))
        self.commit()

    def skor_run(self, run_id: int) -> list[dict[str, Any]]:
        rows = self.con.execute(
            "SELECT s.*, t.slug AS slug, t.nama AS nama, t.pilar AS pilar FROM skor s JOIN topik t ON t.id = s.topik_id "
            "WHERE s.run_id = ? ORDER BY s.peringkat",
            (run_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = self._dec("skor", r) or {}
            d.update(slug=r["slug"], nama=r["nama"], pilar=r["pilar"])
            out.append(d)
        return out

    # ------------------------------------------------------------------------------------ momen, performa, sumber
    def upsert_momen(self, m: dict[str, Any]) -> int:
        return self.upsert("momen", m, ("tanggal", "nama"))

    def momen_antara(self, d1: dt.date, d2: dt.date) -> list[dict[str, Any]]:
        """momen yang BERIRISAN dengan [d1, d2] (termasuk peristiwa berlangsung yang mulai sebelum d1)."""
        return self.daftar(
            "momen",
            "tanggal <= ? AND COALESCE(selesai, tanggal) >= ?",
            (d2.isoformat(), d1.isoformat()),
            urut="tanggal, nama",
        )

    def upsert_performa(self, p: dict[str, Any]) -> int:
        return self.upsert("performa", p, ("kode", "tanggal"))

    def performa_pilar(self) -> dict[str, dict[str, float]]:
        """pilar -> {n, tayangan_median, retensi_rata} dari data performa TERBARU per video."""
        q = (
            "SELECT p.* FROM performa p JOIN (SELECT kode, MAX(tanggal) tg FROM performa GROUP BY kode) z "
            "ON z.kode = p.kode AND z.tg = p.tanggal WHERE p.pilar IS NOT NULL"
        )
        agg: dict[str, list[tuple[float, float]]] = {}
        for r in self.con.execute(q).fetchall():
            agg.setdefault(r["pilar"], []).append((float(r["tayangan"] or 0), float(r["persen_ditonton"] or 0)))
        out = {}
        for p, v in agg.items():
            tay = sorted(x[0] for x in v)
            out[p] = {
                "n": float(len(v)),
                "tayangan_median": tay[len(tay) // 2],
                "retensi_rata": sum(x[1] for x in v) / len(v),
            }
        return out

    def simpan_sumber(self, topik_id: int, items: Iterable[dict[str, Any]]) -> int:
        n = 0
        for it in items:
            it = self.saring(it)
            if not it or not it.get("url") or not it.get("judul"):
                continue
            self.upsert("sumber_ilmiah", {**it, "topik_id": topik_id}, ("topik_id", "url"))
            n += 1
        self.commit()
        return n

    def sumber_topik(self, topik_id: int) -> list[dict[str, Any]]:
        return self.daftar(
            "sumber_ilmiah", "topik_id = ?", (topik_id,), urut="kredibel DESC, COALESCE(kutipan, 0) DESC, id"
        )

    def ganti_rencana_usulan(self, d1: dt.date, d2: dt.date, rows: Sequence[dict[str, Any]]) -> int:
        """usulan lama di rentang diganti; entri 'terkunci'/'selesai' milik pemilik TIDAK disentuh."""
        self.con.execute(
            "DELETE FROM rencana WHERE status = 'usulan' AND tanggal BETWEEN ? AND ?", (d1.isoformat(), d2.isoformat())
        )
        n = 0
        for r in rows:
            ada = self.con.execute(
                "SELECT 1 FROM rencana WHERE tanggal = ? AND jam = ? AND format = ?",
                (r["tanggal"], r["jam"], r["format"]),
            ).fetchone()
            if not ada:
                self.sisip("rencana", r)
                n += 1
        self.commit()
        return n

    # ------------------------------------------------------------------------------------ cari (FTS5)
    def _indeks_ulang(self) -> None:
        self.con.execute("DELETE FROM cari_pustaka")
        for e in self.daftar("episode"):
            t = self.ambil("topik", id=e["topik_id"]) if e.get("topik_id") else None
            bagian = [e.get("sudut") or "", e.get("catatan") or ""]
            if t:
                bagian += [t["nama"], " ".join(t["kata_kunci"])]
            self.con.execute(
                "INSERT INTO cari_pustaka VALUES (?, ?, ?, ?)",
                ("episode", e["kode"], e.get("judul") or "", " ".join(x for x in bagian if x)),
            )
        for m in self.daftar("metadata"):
            self.con.execute(
                "INSERT INTO cari_pustaka VALUES (?, ?, ?, ?)",
                ("metadata", str(m["id"]), " | ".join(m["judul"]), m["deskripsi"] + " " + " ".join(m["tag"])),
            )
        for t in self.daftar("topik"):
            self.con.execute(
                "INSERT INTO cari_pustaka VALUES (?, ?, ?, ?)",
                ("topik", t["slug"], t["nama"], " ".join(t["kata_kunci"] + t["aspek"]) + " " + t["status"]),
            )

    def cari(self, q: str, batas: int = 20) -> list[dict[str, Any]]:
        self._indeks_ulang()
        kata = [w for w in teks.norm(q).split() if w]
        if not kata:
            return []
        ekspr = " ".join(f'"{w}"*' for w in kata)
        rows = self.con.execute(
            "SELECT jenis, kunci, judul, snippet(cari_pustaka, 3, '[', ']', ' ... ', 8) AS cuplik, "
            "bm25(cari_pustaka) AS skor FROM cari_pustaka WHERE cari_pustaka MATCH ? "
            "ORDER BY skor LIMIT ?",
            (ekspr, batas),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------------------------ pemeliharaan
    def bersihkan_blokir(self) -> dict[str, int]:
        """hapus SEMUA data terblokir yang (mungkin) terlanjur ada: topik, snapshot, metadata, sumber, momen."""
        b = self._blokir()
        hasil = {"topik": 0, "snapshot": 0, "metadata": 0, "sumber": 0, "momen": 0}
        for t in self.daftar("topik"):
            if teks.diblokir(t["nama"], b):
                self.con.execute("DELETE FROM topik WHERE id = ?", (t["id"],))
                hasil["topik"] += 1
        for s in self.daftar("snapshot_pencarian"):
            bersih = self.saring(s["data"]) if not teks.diblokir(s["kueri"], b) else None
            if bersih is None:
                self.con.execute("DELETE FROM snapshot_pencarian WHERE id = ?", (s["id"],))
                hasil["snapshot"] += 1
            elif bersih != s["data"]:
                self.ubah("snapshot_pencarian", s["id"], data=bersih)
                hasil["snapshot"] += 1
        for m in self.daftar("metadata"):
            if self.saring({"j": " ".join(m["judul"]), "d": m["deskripsi"], "t": " ".join(m["tag"])}) is None:
                self.con.execute("DELETE FROM metadata WHERE id = ?", (m["id"],))
                hasil["metadata"] += 1
        for s in self.daftar("sumber_ilmiah"):
            if teks.diblokir(s["judul"], b):
                self.con.execute("DELETE FROM sumber_ilmiah WHERE id = ?", (s["id"],))
                hasil["sumber"] += 1
        for m in self.daftar("momen"):
            if teks.diblokir(m["nama"], b):
                self.con.execute("DELETE FROM momen WHERE id = ?", (m["id"],))
                hasil["momen"] += 1
        self.commit()
        return hasil

    def statistik(self) -> dict[str, int]:
        return {t.nama: self.hitung(t.nama) for t in skema.TABEL}

    def ekspor(self, folder: Path | str = EKSPOR_DIR, dengan_snapshot: bool = False) -> dict[str, int]:
        """tulis tiap tabel sebagai JSONL terurut (deterministik, ramah git)."""
        f = Path(folder)
        f.mkdir(parents=True, exist_ok=True)
        out = {}
        for t in skema.TABEL:
            if t.nama in TANPA_EKSPOR and not dengan_snapshot:
                continue
            rows = self.daftar(t.nama)
            (f / f"{t.nama}.jsonl").write_text("".join(_json(r) + "\n" for r in rows), encoding="utf-8")
            out[t.nama] = len(rows)
        (f / "VERSI").write_text(f"{skema.VERSI_SKEMA}\n", encoding="utf-8")
        return out

    def impor(self, folder: Path | str = EKSPOR_DIR) -> dict[str, int]:
        """pulihkan dari ekspor JSONL (id dipertahankan). Tabel yang ada di ekspor dikosongkan dulu."""
        f = Path(folder)
        out = {}
        self.con.execute("PRAGMA foreign_keys = OFF")
        try:
            for t in skema.TABEL:
                p = f / f"{t.nama}.jsonl"
                if not p.exists():
                    continue
                self.con.execute(f"DELETE FROM {t.nama}")
                n = 0
                for ln in p.read_text(encoding="utf-8").splitlines():
                    if ln.strip():
                        self.sisip(t.nama, json.loads(ln))
                        n += 1
                out[t.nama] = n
            self.con.commit()
        finally:
            self.con.execute("PRAGMA foreign_keys = ON")
        bad = self.con.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            raise sqlite3.IntegrityError(f"ekspor tidak konsisten (foreign key): {bad[:3]}")
        return out
