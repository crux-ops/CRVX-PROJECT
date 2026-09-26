"""kliktahu/analisis.py - ANALISIS MENYELURUH & MENDALAM (orchestrator tahap 1-12).

Satu perintah menjalankan seluruh rantai, dari "cari" sampai "teks siap tempel":

  1. KUMPULKAN   pencarian multi-sumber real-time (cari.py): autocomplete Google/YouTube, Wikipedia
                 (judul kanonik, pageview, artikel teratas), berita (Google News/GDELT), Google Trends,
                 jurnal (OpenAlex/Crossref/Europe PMC), momen live (BMKG/USGS/NOAA/JPL/EONET) + cuaca,
                 web (Brave/SearXNG) & pesaing YouTube bila kuncinya diisi - dengan kuota & rantai cadangan
  2. SAHIKAN     semua input lewat validasi.py (tipe, rentang, URL, waktu berzona, kredibilitas TIDAK bawaan)
  3. SEGARKAN    tiap sumber distempel status kesegarannya (kesegaran.py) - umur data ikut dilaporkan
  4. TEMUKAN     kandidat topik dari pertanyaan & sinyal live (penemuan.py), bukan hanya dari registri
  5. BUKTIKAN    klaim dipetakan ke bukti; fakta/inferensi/sinyal minat dibedakan (klaim.py)
  6. NILAI       skor niche yang bisa dijelaskan + keyakinan + rentang (niche.py)
  7. PUTUSKAN    pilih niche/topik/format + sudut + hook, transparan bila juara skor dilewati
  8. TULIS       judul (3), deskripsi (setia bukti, bab bila timeline ada), hashtag, tag (meta/)
  9. CATAT       jejak audit (observabilitas.py) + laporan Markdown

Mode: online (internet langsung) | uji (transport palsu deterministik) | agen (berkas data agen).
TIDAK membuat video, TIDAK menjalankan server: ini pustaka + CLI (`python3 -m kliktahu analisis|cari`).
"""

from __future__ import annotations

import datetime as dt
import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import ROOT, teks
from . import kanal as kanal_mod
from . import kesegaran as G
from . import klaim as KLM
from . import metadata as meta_mod
from . import momen as M
from . import niche as N
from . import observabilitas as O
from . import penemuan as P
from . import skor as S
from .cari import (
    BERITA,
    CUACA,
    ILMIAH,
    MOMEN,
    PESAING,
    SARAN,
    TREN,
    WIKI,
    Hasil,
    Pencari,
    PencariAgen,
    kueri_ilmiah,
)
from .riset.agen import muat as muat_agen
from .riset.http import KlienRiset
from .tema import BENCANA, DAFTAR, TEMA, relevan

UTC = dt.UTC
LAPORAN = ROOT / "laporan"
AUDIT = ROOT / "data" / "audit"
PILAR = ("tubuh", "antariksa", "bumi", "hewan", "teknologi", "misteri")
MAKS_KANDIDAT = 18
DALAM_MAKS = 6  # kandidat yang diukur dengan kuerinya sendiri (analisis mendalam, dibatasi kuota)


@dataclass
class Analisis:
    kueri: str
    mode: str
    tanggal: str
    kandidat: list[P.Kandidat] = field(default_factory=list)
    klaim: list[KLM.Klaim] = field(default_factory=list)
    status: list[G.Status] = field(default_factory=list)
    hasil: list[Hasil] = field(default_factory=list)
    topik: str = ""
    pilar: str = ""
    skor: N.SkorNiche | None = None
    paket: meta_mod.Paket | None = None
    alasan: list[str] = field(default_factory=list)
    peringatan: list[str] = field(default_factory=list)
    cakupan: list[str] = field(default_factory=list)
    sampingan: list[tuple[str, float, float]] = field(default_factory=list)
    detik: float = 0.0
    permintaan: int = 0
    jejak: O.Jejak | None = None
    laporan: Path | None = None

    def dict(self) -> dict[str, Any]:
        return {
            "kueri": self.kueri,
            "mode": self.mode,
            "tanggal": self.tanggal,
            "topik": self.topik,
            "pilar": self.pilar,
            "skor": self.skor.baris() if self.skor else None,
            "kandidat": [k.baris() for k in self.kandidat],
            "klaim": [k.baris() for k in self.klaim],
            "status": [s.baris() for s in self.status],
            "alasan": self.alasan,
            "peringatan": self.peringatan,
            "cakupan": self.cakupan,
            "sampingan": [{"nama": n, "skor": round(sk, 1), "keyakinan": round(yk, 3)} for n, sk, yk in self.sampingan],
            "detik": self.detik,
            "permintaan": self.permintaan,
            "metadata": {
                "judul": self.paket.judul if self.paket else [],
                "hashtag": self.paket.hashtag if self.paket else [],
                "tag": self.paket.tag if self.paket else [],
                "tag_karakter": self.paket.tag_karakter if self.paket else 0,
                "deskripsi": self.paket.deskripsi if self.paket else "",
                "lint_lulus": self.paket.lulus if self.paket else None,
            },
            "laporan": str(self.laporan) if self.laporan else None,
        }


# ================================================================================================ pengumpulan
def kueri_untuk_tema(tema: str, k: kanal_mod.Kanal) -> list[str]:
    """kueri pencarian untuk tema registri: benih x kata kunci + kata inti."""
    t = TEMA.get(tema)
    if not t:
        return [tema]
    out = [f"{b} {kw}" for b in k.riset.benih for kw in t.kata]
    return list(dict.fromkeys(out))


def _pencari(
    mode: str,
    k: kanal_mod.Kanal,
    hari: dt.date,
    agen: Mapping[str, object] | Path | str | None,
    klien: KlienRiset | None,
) -> tuple[Pencari | PencariAgen, KlienRiset | None]:
    """bangun pencari sesuai mode. uji = transport palsu deterministik (tanpa jaringan)."""
    if mode == "agen":
        if not agen:
            raise ValueError("mode agen butuh berkas data agen (--agen <file.json>)")
        data = dict(agen) if isinstance(agen, Mapping) else muat_agen(agen)
        return PencariAgen(data, k, hari), None
    if klien is None:
        if mode == "uji":
            from .riset.fixture import transport_uji

            klien = KlienRiset(k, transport=transport_uji(hari), pakai_cache=False, tidur=lambda s: None)
        else:
            klien = KlienRiset(k)
    return Pencari(klien, k, hari, mode), klien


def kumpulkan(
    pencari: Pencari | PencariAgen,
    kueri: str,
    k: kanal_mod.Kanal,
    tema: str | None = None,
    jenis: Sequence[str] = (SARAN, WIKI, BERITA, TREN, MOMEN, CUACA, ILMIAH, PESAING),
) -> list[Hasil]:
    """cari `kueri` (dan turunan tema bila ada) ke semua sumber; hasil sudah dideduplikasi."""
    out: list[Hasil] = []
    for j in jenis:
        lap = pencari.cari(kueri, j)
        out += lap.hasil
    if tema:
        for q in kueri_untuk_tema(tema, k)[:12]:
            out += pencari.cari(q, SARAN).hasil
            break_out = False  # jangan membanjiri server: cukup sedikit kueri turunan
            if break_out:
                break
        out += pencari.cari(kueri_ilmiah(tema), ILMIAH).hasil
        t = TEMA.get(tema)
        if t:
            out += pencari.cari(t.wiki.replace("_", " "), WIKI).hasil
            out += pencari.cari(t.inti, BERITA).hasil
    seen: set[tuple[str, str]] = set()
    unik = []
    for h in out:
        kk = h.kunci()
        if kk in seen:
            continue
        seen.add(kk)
        unik.append(h)
    return unik


# ================================================================================================ penilaian
def _sebut(nama: str, h: Hasil) -> bool:
    """apakah temuan ini menyebut kandidat `nama`?"""
    n = teks.norm(h.judul)
    if not n:
        return False
    nn = teks.norm(nama)
    if nn and nn in n:
        return True
    return any(teks.kata_utuh_semua(w, n) for w in nn.split() if len(w) >= 4)


def _sebut_kuat(nama: str, h: Hasil) -> bool:
    """seperti `_sebut`, tapi butuh kecocokan UTUH: nama lengkap, atau >= 2 kata isi.

    `_sebut` sengaja longgar untuk mengumpulkan bukti (ingat tinggi). Gerbang CAKUPAN kueri
    tidak boleh longgar: kalau tidak, satu kata umum ("hari", "gunung") saja sudah cukup
    memasukkan kandidat yang sama sekali bukan topik kueri (mis. momen kalender) ke babak final.
    """
    n = teks.norm(h.judul)
    nn = teks.norm(nama)
    if not nn or not n:
        return False
    if nn in n:
        return True
    t = TEMA.get(nama)
    for frasa in (*(t.kata if t else ()), nn):  # frasa utuh (mis. "gunung meletus") = kecocokan kuat
        f = teks.norm(frasa)
        if len(f.split()) >= 2 and f in n:
            return True
    kata = [w for w in nn.split() if len(w) >= 4]
    if not kata:
        return any(teks.kata_utuh_semua(w, n) for w in nn.split())
    return sum(1 for w in kata if teks.kata_utuh_semua(w, n)) >= min(2, len(kata))


def _skor_momen_kandidat(
    nama: str, daftar: Sequence[M.Momen], hari: dt.date, jendela: int
) -> tuple[float, M.Momen | None]:
    """skor momen untuk kandidat (registri memakai SINONIM/HOMONIM; di luar registri pakai kecocokan kata)."""
    t = TEMA.get(nama)
    if t is not None:
        return M.skor_tema(nama, list(daftar), hari, jendela)
    kata = {w for w in teks.norm(nama).split() if len(w) >= 4}
    terbaik: tuple[float, M.Momen | None] = (0.0, None)
    perlu = min(2, len(kata))  # 1 kata umum (mis. "gunung") TIDAK cukup mengklaim momen topik lain
    for m in daftar:
        teks_momen = teks.norm(" ".join([m.nama, *m.tema]))
        cocok = [w for w in kata if teks.kata_utuh_semua(w, teks_momen)]
        if len(cocok) < perlu:
            continue
        s = M.skor_momen(m, hari, jendela)
        if s > terbaik[0]:
            terbaik = (s, m)
    return terbaik


def nilai_kandidat(
    kand: P.Kandidat,
    hasil: Sequence[Hasil],
    k: kanal_mod.Kanal,
    hari: dt.date,
    daftar_momen: Sequence[M.Momen],
    sudah: Sequence[str],
    pilar_bobot: Mapping[str, float] | None = None,
    permintaan_kosong: float | None = None,
) -> tuple[N.SkorNiche, list[KLM.Klaim], dict[str, Any]]:
    """nilai satu kandidat -> (skor niche, klaim terverifikasi, rincian)."""
    terkait = [h for h in hasil if _sebut(kand.nama, h)]
    frasa = [h.judul for h in terkait if h.jenis == SARAN]
    wiki = next((h for h in terkait if h.jenis == WIKI and (h.metrik or 0) > 0), None)
    berita = next((h for h in terkait if h.jenis == BERITA and h.mentah), None)
    tren = max((h.metrik or 0.0) for h in terkait if h.jenis == TREN) if any(h.jenis == TREN for h in terkait) else None
    ilmiah = [h.mentah for h in terkait if h.jenis == ILMIAH and h.mentah]
    ms, ev = _skor_momen_kandidat(kand.nama, daftar_momen, hari, k.jadwal.jendela_momen_hari)

    bukti = KLM.dari_sumber(ilmiah, k.sumber_kredibel)
    klaim_teks = KLM.klaim_dari_frasa(frasa, batas=4)
    if not klaim_teks and frasa:
        klaim_teks = [frasa[0]]
    klaim = [KLM.verifikasi(t, bukti, k.sumber_kredibel) for t in klaim_teks] if klaim_teks else []
    n_kred = sum(1 for b in bukti if b.kredibel)

    t = TEMA.get(kand.nama)
    vis = t.visb if t else 0.5
    bobot_pilar = (pilar_bobot or {}).get(kand.pilar, 0.5) * float(k.pilar.get(kand.pilar, 1.0)) if kand.pilar else 0.4
    mirip = max((teks.mirip(kand.nama, s) / 100.0 for s in sudah), default=0.0)
    kecocokan = 0.5 * kand.skor_kecocokan + 0.3 * vis + 0.2 * min(1.0, bobot_pilar)
    lonjakan = next(
        (
            float(h.mentah["lonjakan_z"])
            for h in terkait
            if h.jenis == WIKI and h.mentah and h.mentah.get("lonjakan_z") is not None
        ),
        None,
    )
    mom = S.momentum(
        None,
        (berita.mentah or {}).get("rasio") if berita else None,
        tren or None,
        lonjakan,
    )
    bkt = S.bukti(n_kred) if ilmiah else None
    permintaan = min(1.0, len(frasa) / 25.0) if frasa else permintaan_kosong
    komponen = N.komponen_dasar(
        permintaan=permintaan,
        momentum=mom[0] if mom else None,
        kecocokan=min(1.0, kecocokan),
        kesegaran=S.kesegaran("segar", mirip)[0],
        bukti=bkt[0] if bkt else None,
        biaya=1.0 - N.biaya_produksi(vis, "shorts", ada_sumber=bool(bukti), di_registri=kand.di_registri),
        waktu=ms if (ms or ev) else None,
        yakin={
            "permintaan": 1.0 if (frasa or permintaan_kosong is not None) else 0.0,
            "bukti": 1.0 if bkt else 0.0,
            "momentum": 1.0 if mom else 0.0,
        },
    )
    catatan = [c.strip() for c in kand.catatan.split(";") if c.strip()]
    skor = N.skor_niche(kand.nama, kand.pilar, komponen, tanpa=() if k.riset.pesaing else ("celah",), catatan=catatan)
    rinci = {
        "frasa": frasa[:12],
        "bukti": [b.baris() for b in bukti[:5]],
        "momen": ev.nama if ev else None,
        "momen_tanggal": ev.tanggal.isoformat() if ev else None,
        "wiki": wiki.metrik if wiki else None,
        "tren": tren,
        "n_bukti_kredibel": n_kred,
    }
    return skor, klaim, rinci


# ================================================================================================ alur utama
def jalankan(
    kueri: str,
    mode: str = "uji",
    hari: dt.date | None = None,
    tema: str | None = None,
    kanal: kanal_mod.Kanal | None = None,
    agen: Mapping[str, object] | Path | str | None = None,
    sudah: Sequence[str] = (),
    pilar_bobot: Mapping[str, float] | None = None,
    folder_laporan: Path | None = None,
    log: Callable[[str], None] = lambda s: None,
    dalam: bool = True,
) -> dict[str, Any]:
    """jalankan seluruh rantai analisis. Mengembalikan kamus ringkas (lihat `Analisis.dict`)."""
    t0 = time.perf_counter()
    k = kanal or kanal_mod.muat()
    hari = hari or G.sekarang().date()
    jejak = O.Jejak(nama=f"analisis:{kueri[:40]}")
    a = Analisis(kueri=kueri, mode=mode, tanggal=hari.isoformat(), jejak=jejak)

    with jejak.tahap("kumpulkan", kueri=kueri, mode=mode):
        pencari, klien = _pencari(mode, k, hari, agen, None)
        hasil = kumpulkan(pencari, kueri, k, tema)
        a.hasil = hasil
        a.status = list(pencari.status)
        a.permintaan = sum(pencari.pakai.values()) if hasattr(pencari, "pakai") else 0
        for st in a.status:
            jejak.sumber(st)
        for c in getattr(pencari, "catatan", []):
            if not c.ok:
                jejak.galat("sumber", c.alasan, sumber=c.sumber, jenis_data=c.jenis)
        log(f"[analisis] {len(hasil)} temuan, {a.permintaan} permintaan, {pencari.ringkas()}")

    # 2-3. sahikan & stempel kesegaran sudah di dalam adaptor; di sini hanya saring yang diblokir/sensitif
    bersih: list[Hasil] = []
    dibuang = 0
    for temuan in hasil:
        n = teks.norm(temuan.judul)
        if teks.diblokir(n, k.aturan.blokir):
            dibuang += 1
            continue
        if teks.sensitif(n, k.aturan.sensitif) and temuan.jenis != SARAN:
            dibuang += 1
            continue
        bersih.append(temuan)
    a.hasil = bersih
    if dibuang:
        a.peringatan.append(f"{dibuang} temuan dibuang (topik diblokir / kata sensitif)")

    with jejak.tahap("temukan"):
        kandidat = P.dari_hasil(bersih, k.niche)
        a.kandidat = P.kanonisasi(P.gabung(kandidat))[: k.analisis.maks_kandidat]
        # CAKUPAN = kandidat yang benar-benar disebut hasil autocomplete kueri utama. Kandidat di luar ini
        # (artikel Wikipedia teratas, momen live, tren) tetap dilaporkan sebagai "sinyal lain", tetapi tidak
        # ikut memutuskan topik: kalau pemilik bertanya "bintang berkedip", jawabannya bukan "gempa bumi".
        saran_utama = [h for h in bersih if h.jenis == SARAN]
        cakupan = {kk.nama for kk in a.kandidat if any(_sebut_kuat(kk.nama, h) for h in saran_utama)}
        a.cakupan = sorted(cakupan)
        log(f"[analisis] {len(a.kandidat)} kandidat topik ({len(cakupan)} dalam cakupan kueri)")

    with jejak.tahap("dalami"):
        # analisis MENDALAM: tiap kandidat dalam cakupan diukur dengan kuerinya sendiri (bukan hanya kueri awal)
        for kk in [x for x in a.kandidat if x.nama in cakupan][: k.analisis.dalam_maks]:
            t = TEMA.get(kk.nama)
            q = f"kenapa {t.inti}" if t else f"kenapa {kk.nama}"
            for temuan in pencari.cari(q, SARAN).hasil:
                if _sebut(kk.nama, temuan):
                    bersih.append(temuan)
            if t:
                bersih += [h for h in pencari.cari(t.wiki.replace("_", " "), WIKI).hasil if _sebut(kk.nama, h)]
            bersih += [h for h in pencari.cari(kueri_ilmiah(kk.nama), ILMIAH).hasil if _sebut(kk.nama, h)]
    # catat pemakaian sumber SETELAH semua kueri turunan selesai. `pencari.pakai` itu penghitung
    # KUMULATIF: kalau dicatat di dalam loop per kandidat, jumlahnya berlipat (dulu 203 vs 111 nyata).
    for id_sumber, jumlah in pencari.pakai.items():
        jejak.pakai(id_sumber, jumlah)
    a.status = list(pencari.status)
    a.permintaan = sum(pencari.pakai.values())

    with jejak.tahap("nilai"):
        # momen live sudah berubah jadi Hasil saat dikumpulkan -> buat lagi objek Momen untuk dicocokkan
        momen_live: list[M.Momen] = []
        for temuan in bersih:
            if temuan.jenis in (MOMEN, CUACA) and temuan.terbit:
                try:
                    tanggal_momen = dt.date.fromisoformat(temuan.terbit[:10])
                except (ValueError, TypeError):
                    continue
                # tema momen berasal dari SUMBERNYA (mentah) atau dari isi judulnya sendiri.
                # JANGAN dari nama kandidat: nanti tiap kandidat "punya momen" sendiri dan
                # momen Semeru bisa diklaim kandidat Erebus (lingkaran yang menguatkan diri).
                tema_momen = [str(x) for x in (temuan.mentah or {}).get("tema", []) if x]
                if not tema_momen:
                    tema_momen = [t.nama for t in DAFTAR if relevan(temuan.judul, t)][:4]
                momen_live.append(
                    M.Momen(
                        tanggal_momen,
                        temuan.judul,
                        tema_momen,
                        "live",
                        temuan.sumber,
                        float(temuan.metrik or 0.5),
                    )
                )
        semua_momen = M.semua(hari, 120, momen_live)
        nilai: list[tuple[N.SkorNiche, list[KLM.Klaim], dict[str, Any], P.Kandidat]] = []
        for kand in a.kandidat:
            sk, kl, rinci = nilai_kandidat(kand, bersih, k, hari, semua_momen, sudah, pilar_bobot)
            nilai.append((sk, kl, rinci, kand))
        # pencarian jelas menghasilkan frasa untuk sebagian kandidat -> kandidat yang TIDAK punya frasa
        # berarti tidak dicari orang (bukan "belum diukur"): permintaannya dibedakan dari netral 0.5
        if any(z[2]["frasa"] for z in nilai):
            baru: list[tuple[N.SkorNiche, list[KLM.Klaim], dict[str, Any], P.Kandidat]] = []
            for z in nilai:
                if z[2]["frasa"]:
                    baru.append(z)
                else:
                    sk2, kl2, r2 = nilai_kandidat(
                        z[3],
                        bersih,
                        k,
                        hari,
                        semua_momen,
                        sudah,
                        pilar_bobot,
                        permintaan_kosong=k.analisis.permintaan_kosong,
                    )
                    baru.append((sk2, kl2, r2, z[3]))
            nilai = baru
        nilai.sort(key=lambda z: (-z[0].skor, -z[0].keyakinan))
        utama: list[tuple[N.SkorNiche, list[KLM.Klaim], dict[str, Any], P.Kandidat]] = []
        if cakupan:
            utama = [z for z in nilai if z[3].nama in cakupan]
            a.sampingan = [(z[0].nama, z[0].skor, z[0].keyakinan) for z in nilai if z[3].nama not in cakupan]
        else:
            utama = list(nilai)

    if not utama:
        a.peringatan.append("tidak ada kandidat yang bisa dinilai dari data yang tersedia")
        a.detik = round(time.perf_counter() - t0, 3)
        jejak.tutup()
        return a.dict()

    with jejak.tahap("putuskan"):
        peta = {z[0].nama: (z[2].get("momen_tanggal") and dt.date.fromisoformat(z[2]["momen_tanggal"])) for z in utama}
        pilihan, alasan = N.pilih(
            [z[0] for z in utama],
            hari,
            {kk: v for kk, v in peta.items() if v},
            batas_selisih=k.analisis.batas_selisih,
        )
        assert pilihan is not None
        idx = next(i for i, z in enumerate(utama) if z[0].nama == pilihan.nama)
        skor, klaim, rinci, kand = utama[idx]
        a.topik, a.pilar, a.skor = skor.nama, skor.pilar, skor
        a.klaim = klaim
        a.alasan = [*alasan, *N.jelaskan(skor)]
        if kand.catatan and kand.catatan not in a.peringatan:
            a.peringatan.append(kand.catatan)
        if skor.keyakinan < 0.5:
            a.peringatan.append(
                f"Keyakinan {skor.keyakinan:.0%} (< 50%): sebagian komponen belum berdata. "
                "Jalankan riset online atau lengkapi data agen sebelum memakai keputusan ini."
            )
        if a.topik in BENCANA:
            a.peringatan.append(
                f"Topik bencana dengan korban jiwa nyata: bahas sainsnya dengan hormat, tanpa sensasi; "
                f"arahkan ke info resmi {BENCANA[a.topik]}."
            )
        if rinci.get("momen"):
            a.alasan.append(f"Momen terdekat: {rinci['momen']} ({rinci.get('momen_tanggal')}).")
        jejak.putus(topik=a.topik, pilar=a.pilar, skor=skor.skor, keyakinan=skor.keyakinan, mode=mode)
        log(f"[analisis] putus: {a.topik} ({a.pilar}) {skor.skor:.1f}")

    with jejak.tahap("metadata"):
        t = TEMA.get(a.topik)
        inti = t.inti if t else a.topik
        frasa = [f for f in rinci.get("frasa", []) if not teks.sensitif(f, k.aturan.sensitif)]
        if not frasa:
            frasa = [f"kenapa {inti}"]
        sudut = [f for f in frasa if len(f.split()) >= 4][:3]
        sumber = [b for b in rinci.get("bukti", []) if b.get("kredibel")][:4]
        status_sumber = G.ringkas(a.status)
        a.paket = meta_mod.buat(
            a.topik,
            frasa,
            "shorts",
            k,
            hook=None,
            sumber=sumber,
            momen=M.nama_pendek(rinci.get("momen") or "") if rinci.get("momen") else None,
            sudut=sudut,
            bukti=[dict(b) for b in sumber],
            tanggal_riset=a.tanggal,
            status_sumber=status_sumber,
        )
        if not a.paket.lulus:
            a.peringatan.append("draf metadata belum lulus lint: " + "; ".join(a.paket.galat[:3]))
        a.peringatan += [p for p in a.paket.peringatan if p not in a.peringatan]

    a.detik = round(time.perf_counter() - t0, 3)
    jejak.tutup()
    folder = folder_laporan or (LAPORAN / "_uji" if mode == "uji" else LAPORAN)
    a.laporan = tulis_laporan(a, rinci, folder)
    if mode != "uji" and k.analisis.tulis_audit:
        try:
            AUDIT.mkdir(parents=True, exist_ok=True)
            jejak.tulis(AUDIT / f"analisis_{a.tanggal}.jsonl")
        except OSError as e:  # audit tidak boleh menggagalkan analisis
            log(f"[analisis] audit gagal ditulis: {e}")
    return a.dict()


# ================================================================================================ laporan
def tulis_laporan(a: Analisis, rinci: Mapping[str, Any], folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    L = [
        f"# ANALISIS MENDALAM - {a.kueri}",
        "",
        f"Tanggal {a.tanggal} | mode {a.mode} | {a.detik} s | {a.permintaan} permintaan",
        "",
        "## Keputusan",
        "",
        f"**{a.topik}** (pilar {a.pilar or '-'})"
        + (
            f" - skor niche {a.skor.skor:.1f} (rentang {a.skor.rentang[0]:.0f}-{a.skor.rentang[1]:.0f}, "
            f"keyakinan {a.skor.keyakinan:.0%})"
            if a.skor
            else ""
        ),
        "",
        *[f"- {x}" for x in a.alasan],
    ]
    if a.peringatan:
        L += ["", "### Peringatan", *[f"- {x}" for x in a.peringatan]]
    L += ["", "## Kandidat topik (penemuan)", "", *P.ringkas(a.kandidat), "", P.batas_registri(a.kandidat)]
    if a.cakupan:
        L += [
            "",
            "### Cakupan kueri",
            "",
            f"Kandidat yang benar-benar disebut hasil pencarian untuk kueri ini: {', '.join(a.cakupan)}. "
            "Kandidat lain (artikel Wikipedia teratas, momen live, tren) tetap dicatat sebagai sinyal lain, "
            "tetapi tidak dipakai menjawab kueri ini.",
        ]
    if a.sampingan:
        L += [
            "",
            "### Sinyal lain (di luar kueri, tidak ikut menentukan)",
            "",
            "| topik | skor | keyakinan |",
            "|---|---|---|",
            *[f"| {n} | {s:.1f} | {y:.0%} |" for n, s, y in a.sampingan[:8]],
        ]
    if a.klaim:
        L += ["", "## Verifikasi klaim", "", *KLM.laporan_md(a.klaim)]
    if a.skor:
        L += ["", "## Papan niche", "", *N.tabel_md([a.skor])]
    L += ["", "## Kesegaran sumber", "", *G.tabel_md(a.status)]
    if a.paket:
        L += [
            "",
            "## Metadata draf (dari hasil analisis)",
            "",
            "Judul:",
            *[f"{i}. {j}" for i, j in enumerate(a.paket.judul, 1)],
            "",
            "```text",
            a.paket.deskripsi.rstrip(),
            "```",
            "",
            f"Hashtag: {' '.join(a.paket.hashtag)}",
            "",
            f"Tag ({a.paket.tag_karakter}/500): {', '.join(a.paket.tag)}",
            "",
            f"Lint draf: {'LULUS' if a.paket.lulus else 'BELUM LULUS - ' + '; '.join(a.paket.galat)}",
        ]
    if a.jejak:
        L += ["", "## Jejak run", "", *a.jejak.tabel_md()]
    p = folder / "ANALISIS.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    (folder / "analisis_terakhir.json").write_text(
        json.dumps(a.dict(), ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    return p
