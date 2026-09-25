"""kliktahu/skema.py - SATU sumber skema basis data -> semua turunan (tidak pernah beda satu sama lain).

Dari definisi TABEL di bawah dihasilkan:
  skema/sqlite.sql                         DDL SQLite (basis data lokal, dipakai kliktahu/db.py)
  skema/postgres.sql                       DDL Postgres untuk Bolt Database / Supabase (+ RLS)
  supabase/migrations/<ts>_kliktahu_v1.sql migrasi siap pakai bila kelak dihubungkan ke Bolt/Supabase
  skema/json/<tabel>.schema.json           JSON Schema 2020-12 (kontrak data)
  skema/ts/src/tipe.ts                     tipe TypeScript (Row/Insert/Update + tipe Database gaya supabase-js)

Tulis ulang:  python3 -m kliktahu skema tulis      Cek tidak melenceng:  python3 -m kliktahu skema cek
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import ROOT

VERSI_SKEMA = 1
PILAR = ("tubuh", "antariksa", "bumi", "hewan", "teknologi", "misteri")
MIGRASI_SUPABASE = "supabase/migrations/20260925000000_kliktahu_v1.sql"


@dataclass(frozen=True)
class Kolom:
    nama: str
    tipe: str  # id | text | int | real | bool | json | waktu | tanggal
    wajib: bool = False
    unik: bool = False
    bawaan: str | None = None  # 'sekarang' | literal SQL ('0', "'segar'", "'[]'")
    ref: str | None = None  # 'topik.id'
    pilihan: tuple[str, ...] | None = None
    ts: str | None = None  # tipe TS untuk kolom json (mis. 'string[]')
    ket: str = ""


@dataclass(frozen=True)
class Tabel:
    nama: str
    ket: str
    kolom: tuple[Kolom, ...]
    unik: tuple[tuple[str, ...], ...] = ()
    indeks: tuple[tuple[str, ...], ...] = ()

    def k(self, nama: str) -> Kolom:
        return next(c for c in self.kolom if c.nama == nama)


def _id() -> Kolom:
    return Kolom("id", "id", ket="kunci utama")


def _waktu(nama: str) -> Kolom:
    return Kolom(nama, "waktu", wajib=True, bawaan="sekarang")


FORMAT = ("shorts", "long")
TABEL: tuple[Tabel, ...] = (
    Tabel(
        "topik",
        "Registri topik/tema kanal (segar, antre, sudah dibahas).",
        (
            _id(),
            Kolom("slug", "text", wajib=True, unik=True, ket="slug unik, mis. hari_tanpa_bayangan"),
            Kolom("nama", "text", wajib=True),
            Kolom("pilar", "text", wajib=True, pilihan=PILAR),
            Kolom("kata_kunci", "json", wajib=True, bawaan="'[]'", ts="string[]", ket="kata[0] = inti"),
            Kolom("aspek", "json", wajib=True, bawaan="'[]'", ts="string[]"),
            Kolom("nama_en", "text", ket="nama Inggris untuk pencarian jurnal"),
            Kolom("wiki", "text", ket="judul artikel Wikipedia bahasa Indonesia"),
            Kolom("evergreen", "bool", wajib=True, bawaan="1"),
            Kolom("visual", "real", wajib=True, bawaan="0.8", ket="seberapa bisa diperlihatkan 0..1"),
            Kolom(
                "status", "text", wajib=True, bawaan="'segar'", pilihan=("segar", "antre", "dibahas", "long", "arsip")
            ),
            Kolom("catatan", "text"),
            _waktu("dibuat"),
            _waktu("diubah"),
        ),
        indeks=(("pilar",), ("status",)),
    ),
    Tabel(
        "episode",
        "Episode Shorts/Long (Ep50, Long03, ...) dan status produksinya.",
        (
            _id(),
            Kolom("kode", "text", wajib=True, unik=True, ket="Ep50 / Long03"),
            Kolom("format", "text", wajib=True, pilihan=FORMAT),
            Kolom("topik_id", "int", ref="topik.id"),
            Kolom("slug", "text", ket="folder episodes/<slug> atau long/<slug>"),
            Kolom("judul", "text", ket="judul terpilih"),
            Kolom("sudut", "text", ket="sudut pembeda"),
            Kolom(
                "status",
                "text",
                wajib=True,
                bawaan="'ide'",
                pilihan=("ide", "riset", "naskah", "vo", "render", "rilis", "arsip"),
            ),
            Kolom("jadwal_tayang", "waktu"),
            Kolom("tayang", "waktu"),
            Kolom("youtube_id", "text"),
            Kolom("durasi_detik", "real"),
            Kolom("catatan", "text"),
            _waktu("dibuat"),
            _waktu("diubah"),
        ),
        indeks=(("status",), ("topik_id",)),
    ),
    Tabel(
        "run_riset",
        "Satu kali jalan mesin riset (online/agen/uji).",
        (
            _id(),
            _waktu("mulai"),
            Kolom("selesai", "waktu"),
            Kolom("mode", "text", wajib=True, pilihan=("online", "agen", "uji", "manual")),
            Kolom("versi", "text", wajib=True),
            Kolom("tanggal", "tanggal", wajib=True, ket="tanggal analisis (WIB)"),
            Kolom("statistik", "json", wajib=True, bawaan="'{}'", ts="{ [key: string]: Json | undefined }"),
            Kolom("catatan", "text"),
        ),
        indeks=(("tanggal",),),
    ),
    Tabel(
        "metadata",
        "Paket metadata (3 judul, deskripsi, hashtag, tag) per topik/episode, berversi.",
        (
            _id(),
            Kolom("topik_id", "int", ref="topik.id"),
            Kolom("episode_id", "int", ref="episode.id"),
            Kolom("run_id", "int", ref="run_riset.id"),
            Kolom("versi", "int", wajib=True, bawaan="1"),
            Kolom("format", "text", wajib=True, pilihan=FORMAT),
            Kolom("kata_kunci", "text", wajib=True, ket="kata kunci utama = baris pertama deskripsi"),
            Kolom("judul", "json", wajib=True, ts="string[]"),
            Kolom("judul_terpilih", "text"),
            Kolom("deskripsi", "text", wajib=True),
            Kolom("hashtag", "json", wajib=True, ts="string[]"),
            Kolom("tag", "json", wajib=True, ts="string[]"),
            Kolom("tag_karakter", "int", wajib=True, ket="hitungan cara YouTube (<= 500)"),
            Kolom("sumber", "json", wajib=True, bawaan="'[]'", ts="Json[]"),
            Kolom("lint", "json", wajib=True, bawaan="'[]'", ts="string[]"),
            Kolom("lulus", "bool", wajib=True, bawaan="0"),
            _waktu("dibuat"),
        ),
        indeks=(("topik_id",), ("episode_id",)),
    ),
    Tabel(
        "snapshot_pencarian",
        "Hasil mentah-ternormalisasi tiap pencarian real-time (untuk VELOCITY & audit).",
        (
            _id(),
            Kolom("run_id", "int", ref="run_riset.id"),
            Kolom(
                "sumber",
                "text",
                wajib=True,
                pilihan=(
                    "google_saran",
                    "youtube_saran",
                    "wikipedia",
                    "berita",
                    "gdelt",
                    "tren",
                    "youtube",
                    "momen",
                    "ilmiah",
                    "web",
                    "agen",
                ),
            ),
            Kolom("kueri", "text", wajib=True),
            Kolom("topik_id", "int", ref="topik.id"),
            _waktu("diambil"),
            Kolom("status", "int", ket="status HTTP (0 = dari data agen/fixture)"),
            Kolom("durasi_ms", "int"),
            Kolom("dari_cache", "bool", wajib=True, bawaan="0"),
            Kolom("jumlah", "int", wajib=True, bawaan="0"),
            Kolom("data", "json", wajib=True, ts="Json"),
            Kolom("sidik", "text", wajib=True, ket="sha1 data (deteksi perubahan)"),
        ),
        indeks=(("sumber", "kueri"), ("run_id",), ("topik_id",)),
    ),
    Tabel(
        "skor",
        "Skor per topik per run: rumus prompt v3-v6 + v7 (peluang & keyakinan).",
        (
            _id(),
            Kolom("run_id", "int", wajib=True, ref="run_riset.id"),
            Kolom("topik_id", "int", wajib=True, ref="topik.id"),
            Kolom("peringkat", "int", wajib=True),
            Kolom("status_topik", "text", wajib=True, pilihan=("segar", "long", "dibahas")),
            Kolom("v3_skor", "real", wajib=True),
            Kolom("v3_tumbuh", "real", wajib=True),
            Kolom("v4_keluarga", "real"),
            Kolom("v5_views", "real", wajib=True),
            Kolom("v6_papan", "real", wajib=True),
            Kolom("v7_peluang", "real", wajib=True),
            Kolom("keyakinan", "real", wajib=True, ket="porsi bobot v7 yang didukung data nyata 0..1"),
            Kolom("komponen", "json", wajib=True, ts="{ [key: string]: number }"),
            Kolom("sinyal", "json", wajib=True, ts="{ [key: string]: Json | undefined }"),
        ),
        unik=(("run_id", "topik_id"),),
        indeks=(("topik_id",),),
    ),
    Tabel(
        "momen",
        "Kalender momen: statis (kurasi), astro (dihitung), live (umpan real-time), agen.",
        (
            _id(),
            Kolom("tanggal", "tanggal", wajib=True),
            Kolom("selesai", "tanggal"),
            Kolom("nama", "text", wajib=True),
            Kolom("tema", "json", wajib=True, ts="string[]"),
            Kolom("jenis", "text", wajib=True, pilihan=("statis", "astro", "live", "agen")),
            Kolom("sumber", "text", wajib=True),
            Kolom("urgensi", "real", wajib=True, bawaan="0", ket="0..1; live penting = 1"),
            Kolom("lokasi", "text"),
            _waktu("dibuat"),
        ),
        unik=(("tanggal", "nama"),),
        indeks=(("tanggal",),),
    ),
    Tabel(
        "performa",
        "Performa video (impor CSV YouTube Studio / manual) -> loop bobot pilar.",
        (
            _id(),
            Kolom("episode_id", "int", ref="episode.id"),
            Kolom("kode", "text", wajib=True, ket="kode episode atau ID video YouTube"),
            Kolom("judul", "text"),
            Kolom("tanggal", "tanggal", wajib=True, ket="tanggal data diambil"),
            Kolom("tayangan", "int", wajib=True, bawaan="0"),
            Kolom("durasi_tonton_jam", "real"),
            Kolom("rata_durasi_detik", "real"),
            Kolom("persen_ditonton", "real", ket="retensi rata-rata %"),
            Kolom("impresi", "int"),
            Kolom("ctr", "real", ket="rasio klik-tayang %"),
            Kolom("subscriber", "int"),
            Kolom("pilar", "text", pilihan=PILAR),
            Kolom("sumber", "text", wajib=True, pilihan=("studio_csv", "performa_csv", "manual", "api")),
        ),
        unik=(("kode", "tanggal"),),
        indeks=(("pilar",),),
    ),
    Tabel(
        "sumber_ilmiah",
        "Sumber kredibel per topik (jurnal, lembaga, ensiklopedia) untuk naskah & deskripsi.",
        (
            _id(),
            Kolom("topik_id", "int", wajib=True, ref="topik.id"),
            Kolom("episode_id", "int", ref="episode.id"),
            Kolom("judul", "text", wajib=True),
            Kolom("url", "text", wajib=True),
            Kolom("penerbit", "text"),
            Kolom("tahun", "int"),
            Kolom("doi", "text"),
            Kolom("jenis", "text", wajib=True, pilihan=("jurnal", "lembaga", "ensiklopedia", "berita", "lain")),
            Kolom("kredibel", "bool", wajib=True, bawaan="0"),
            Kolom("kutipan", "int", ket="jumlah sitasi (OpenAlex)"),
            _waktu("dibuat"),
        ),
        unik=(("topik_id", "url"),),
    ),
    Tabel(
        "rencana",
        "Kalender konten (usulan perencana / terkunci pemilik).",
        (
            _id(),
            Kolom("tanggal", "tanggal", wajib=True),
            Kolom("jam", "text", wajib=True, ket="HH:MM WIB"),
            Kolom("format", "text", wajib=True, pilihan=FORMAT),
            Kolom("topik_id", "int", ref="topik.id"),
            Kolom("episode_kode", "text"),
            Kolom("judul_kerja", "text"),
            Kolom("alasan", "text"),
            Kolom("momen_id", "int", ref="momen.id"),
            Kolom("skor", "real"),
            Kolom("status", "text", wajib=True, bawaan="'usulan'", pilihan=("usulan", "terkunci", "selesai", "batal")),
            _waktu("dibuat"),
        ),
        unik=(("tanggal", "jam", "format"),),
        indeks=(("tanggal",),),
    ),
)
T: dict[str, Tabel] = {t.nama: t for t in TABEL}


# ------------------------------------------------------------------------------------------------ SQLite
def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _bawaan_sqlite(c: Kolom) -> str:
    if c.bawaan is None:
        return ""
    if c.bawaan == "sekarang":
        return " DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
    return f" DEFAULT {c.bawaan}"


def ddl_sqlite() -> str:
    out = [
        f"-- DIHASILKAN OTOMATIS oleh kliktahu/skema.py (versi skema {VERSI_SKEMA}). JANGAN diedit manual.",
        "PRAGMA foreign_keys = ON;",
        "",
    ]
    for t in TABEL:
        baris = []
        for c in t.kolom:
            if c.tipe == "id":
                baris.append(f"  {c.nama} INTEGER PRIMARY KEY")
                continue
            tipe = {
                "text": "TEXT",
                "int": "INTEGER",
                "real": "REAL",
                "bool": "INTEGER",
                "json": "TEXT",
                "waktu": "TEXT",
                "tanggal": "TEXT",
            }[c.tipe]
            s = f"  {c.nama} {tipe}" + (" NOT NULL" if c.wajib else "") + (" UNIQUE" if c.unik else "")
            s += _bawaan_sqlite(c)
            cek = []
            if c.tipe == "bool":
                cek.append(f"{c.nama} IN (0, 1)")
            if c.tipe == "json":
                cek.append(f"json_valid({c.nama})")
            if c.tipe == "tanggal":
                cek.append(f"{c.nama} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
            if c.pilihan:
                cek.append(f"{c.nama} IN ({', '.join(_q(p) for p in c.pilihan)})")
            if cek:
                syarat = " AND ".join(cek)
                s += f" CHECK ({syarat if c.wajib else f'{c.nama} IS NULL OR ({syarat})'})"
            if c.ref:
                rt, rk = c.ref.split(".")
                s += f" REFERENCES {rt}({rk}) ON DELETE {'CASCADE' if c.wajib else 'SET NULL'}"
            baris.append(s)
        for u in t.unik:
            baris.append(f"  UNIQUE ({', '.join(u)})")
        out.append(f"-- {t.ket}\nCREATE TABLE IF NOT EXISTS {t.nama} (\n" + ",\n".join(baris) + "\n);")
        for ix in t.indeks:
            out.append(f"CREATE INDEX IF NOT EXISTS ix_{t.nama}_{'_'.join(ix)} ON {t.nama} ({', '.join(ix)});")
        out.append("")
    out.append("-- pencarian teks penuh pustaka (FTS5, BM25); diisi ulang oleh kliktahu/db.py")
    out.append(
        "CREATE VIRTUAL TABLE IF NOT EXISTS cari_pustaka USING fts5(jenis, kunci, judul, isi, "
        "tokenize = 'unicode61 remove_diacritics 2');"
    )
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------------------------------------ Postgres
def ddl_postgres() -> str:
    out = [
        f"-- DIHASILKAN OTOMATIS oleh kliktahu/skema.py (versi skema {VERSI_SKEMA}). JANGAN diedit manual.",
        "-- Untuk Bolt Database / Supabase (Postgres 15+). Jalankan di SQL editor atau sebagai migrasi.",
        "-- RLS aktif: hanya pengguna terautentikasi & service_role yang bisa membaca/menulis (anon DITOLAK).",
        "",
    ]
    for t in TABEL:
        baris = []
        for c in t.kolom:
            if c.tipe == "id":
                baris.append(f"  {c.nama} bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY")
                continue
            tipe = {
                "text": "text",
                "int": "bigint",
                "real": "double precision",
                "bool": "boolean",
                "json": "jsonb",
                "waktu": "timestamptz",
                "tanggal": "date",
            }[c.tipe]
            s = f"  {c.nama} {tipe}" + (" NOT NULL" if c.wajib else "") + (" UNIQUE" if c.unik else "")
            if c.bawaan == "sekarang":
                s += " DEFAULT now()"
            elif c.bawaan is not None:
                if c.tipe == "bool":
                    s += " DEFAULT " + ("true" if c.bawaan == "1" else "false")
                elif c.tipe == "json":
                    s += f" DEFAULT {c.bawaan}::jsonb"
                else:
                    s += f" DEFAULT {c.bawaan}"
            if c.pilihan:
                s += f" CHECK ({c.nama} IN ({', '.join(_q(p) for p in c.pilihan)}))"
            if c.ref:
                rt, rk = c.ref.split(".")
                s += f" REFERENCES public.{rt}({rk}) ON DELETE {'CASCADE' if c.wajib else 'SET NULL'}"
            baris.append(s)
        for u in t.unik:
            baris.append(f"  UNIQUE ({', '.join(u)})")
        out.append(f"CREATE TABLE IF NOT EXISTS public.{t.nama} (\n" + ",\n".join(baris) + "\n);")
        out.append(f"COMMENT ON TABLE public.{t.nama} IS {_q(t.ket)};")
        for ix in t.indeks:
            out.append(f"CREATE INDEX IF NOT EXISTS ix_{t.nama}_{'_'.join(ix)} ON public.{t.nama} ({', '.join(ix)});")
        out.append(f"ALTER TABLE public.{t.nama} ENABLE ROW LEVEL SECURITY;")
        out.append(f"DROP POLICY IF EXISTS kliktahu_{t.nama}_auth ON public.{t.nama};")
        out.append(
            f"CREATE POLICY kliktahu_{t.nama}_auth ON public.{t.nama} FOR ALL TO authenticated "
            "USING (true) WITH CHECK (true);"
        )
        out.append("")
    out.append(
        "CREATE INDEX IF NOT EXISTS ix_episode_cari ON public.episode USING gin "
        "(to_tsvector('simple', coalesce(kode,'') || ' ' || coalesce(judul,'') || ' ' || coalesce(sudut,'')));"
    )
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------------------------------------ JSON Schema
def _js_tipe(c: Kolom) -> dict:
    if c.tipe in ("id", "int"):
        d: dict = {"type": "integer"}
    elif c.tipe == "real":
        d = {"type": "number"}
    elif c.tipe == "bool":
        d = {"type": "boolean"}
    elif c.tipe == "json":
        d = (
            {"type": "array", "items": {"type": "string"}}
            if c.ts == "string[]"
            else (
                {"type": "array"}
                if (c.ts or "").endswith("[]")
                else ({"type": "object"} if (c.ts or "").startswith("{") else {})
            )
        )
    elif c.tipe == "waktu":
        d = {"type": "string", "format": "date-time"}
    elif c.tipe == "tanggal":
        d = {"type": "string", "format": "date"}
    else:
        d = {"type": "string"}
    if c.pilihan:
        d["enum"] = list(c.pilihan)
    if not c.wajib and c.tipe != "id" and "type" in d:
        d["type"] = [d["type"], "null"]
        if "enum" in d:
            d["enum"] = [*d["enum"], None]
    if c.ket:
        d["description"] = c.ket
    return d


def json_schema(t: Tabel) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://kliktahu.local/skema/{t.nama}.schema.json",
        "title": t.nama,
        "description": t.ket,
        "type": "object",
        "additionalProperties": False,
        "properties": {c.nama: _js_tipe(c) for c in t.kolom},
        "required": [c.nama for c in t.kolom if c.wajib or c.tipe == "id"],
    }


# ------------------------------------------------------------------------------------------------ TypeScript
def _pascal(s: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in s.split("_"))


def _ts_enum_nama(t: Tabel, c: Kolom) -> str:
    if c.pilihan == PILAR:
        return "Pilar"
    if c.pilihan == FORMAT:
        return "Format"
    return _pascal(t.nama) + _pascal(c.nama)


def _ts_tipe(t: Tabel, c: Kolom) -> str:
    if c.pilihan:
        return _ts_enum_nama(t, c)
    return {
        "id": "number",
        "int": "number",
        "real": "number",
        "bool": "boolean",
        "text": "string",
        "waktu": "string",
        "tanggal": "string",
        "json": c.ts or "Json",
    }[c.tipe]


def typescript() -> str:
    out = [
        f"// DIHASILKAN OTOMATIS oleh kliktahu/skema.py (versi skema {VERSI_SKEMA}). JANGAN diedit manual.",
        "// Jalankan ulang: python3 -m kliktahu skema tulis",
        "// Bentuk `Database` cocok dengan generik supabase-js / Bolt Database: createClient<Database>(url, key).",
        "",
        "export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];",
        f"export const VERSI_SKEMA = {VERSI_SKEMA};",
        "",
    ]
    enums: dict[str, tuple[str, ...]] = {}
    for t in TABEL:
        for c in t.kolom:
            if c.pilihan:
                enums[_ts_enum_nama(t, c)] = c.pilihan
    for n, p in enums.items():
        out.append(f"export type {n} = {' | '.join(json.dumps(x) for x in p)};")
    out.append("")
    for t in TABEL:
        P = _pascal(t.nama)
        out.append(f"/** {t.ket} */")
        out.append(f"export interface {P}Row {{")
        for c in t.kolom:
            opt = "" if (c.wajib or c.tipe == "id") else " | null"
            out.append(f"  {c.nama}: {_ts_tipe(t, c)}{opt};")
        out.append("}")
        out.append(f"export interface {P}Insert {{")
        for c in t.kolom:
            boleh_kosong = c.tipe == "id" or not c.wajib or c.bawaan is not None
            opt = "" if (c.wajib or c.tipe == "id") else " | null"
            out.append(f"  {c.nama}{'?' if boleh_kosong else ''}: {_ts_tipe(t, c)}{opt};")
        out.append("}")
        out.append(f"export type {P}Update = Partial<{P}Insert>;")
        out.append("")
    out.append("export interface Database {")
    out.append("  public: {")
    out.append("    Tables: {")
    for t in TABEL:
        P = _pascal(t.nama)
        out.append(f"      {t.nama}: {{ Row: {P}Row; Insert: {P}Insert; Update: {P}Update; Relationships: [] }};")
    out.append("    };")
    out.append("    Views: { [_ in never]: never };")
    out.append("    Functions: { [_ in never]: never };")
    out.append("    Enums: {")
    for n in enums:
        out.append(f"      {n}: {n};")
    out.append("    };")
    out.append("    CompositeTypes: { [_ in never]: never };")
    out.append("  };")
    out.append("}")
    out.append("")
    out.append('export type NamaTabel = keyof Database["public"]["Tables"];')
    out.append(f"export const TABEL: readonly NamaTabel[] = [{', '.join(json.dumps(t.nama) for t in TABEL)}] as const;")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------------------------------------ tulis / cek
def berkas() -> dict[str, str]:
    """path relatif repo -> isi yang seharusnya."""
    pg = ddl_postgres()
    f = {
        "skema/sqlite.sql": ddl_sqlite(),
        "skema/postgres.sql": pg,
        MIGRASI_SUPABASE: pg,
        "skema/ts/src/tipe.ts": typescript(),
    }
    for t in TABEL:
        f[f"skema/json/{t.nama}.schema.json"] = json.dumps(json_schema(t), ensure_ascii=False, indent=2) + "\n"
    from .paritas import fixture_json

    f["skema/ts/fixture/skor_paritas.json"] = fixture_json()
    return f


def tulis(root: Path = ROOT) -> list[str]:
    ditulis = []
    for rel, isi in berkas().items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or p.read_text(encoding="utf-8") != isi:
            p.write_text(isi, encoding="utf-8")
            ditulis.append(rel)
    return ditulis


FIXTURE_PARITAS = "skema/ts/fixture/skor_paritas.json"


def _sama_toleran(a: object, b: object, tol: float = 1e-12) -> bool:
    """bandingkan JSON: angka boleh beda di digit terakhir (libm tanh/log10 beda antar platform), selain itu persis."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol * max(1.0, abs(b))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_sama_toleran(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_sama_toleran(a[k], b[k], tol) for k in a)
    return a == b


def cek(root: Path = ROOT) -> list[str]:
    """daftar berkas turunan yang TIDAK sama dengan skema (kosong = sinkron)."""
    beda = []
    for rel, isi in berkas().items():
        f = root / rel
        if not f.exists():
            beda.append(rel)
            continue
        ada = f.read_text(encoding="utf-8")
        if rel == FIXTURE_PARITAS:
            if not _sama_toleran(json.loads(ada), json.loads(isi)):
                beda.append(rel)
        elif ada != isi:
            beda.append(rel)
    return beda
