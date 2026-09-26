"""kliktahu/metadata.py - GENERATOR METADATA (3 judul, deskripsi, hashtag, tag) dari hasil riset + LINT ketat.

Judul dibentuk dari frasa pencarian ASLI (autocomplete Google/YouTube hasil riset), diberi skor (kata kunci di
depan, panjang ideal layar HP, pola rasa penasaran yang jujur, beda dari judul pesaing) lalu dipilih 3 yang
BERAGAM (MMR). Deskripsi: baris pertama = kata kunci utama, bab/timestamp dari timeline.json, sumber kredibel,
disclaimer kesehatan bila perlu. Tag dihitung CARA YOUTUBE (<= 500). Semua ASCII (aturan METADATA pemilik).

Lint (`python3 -m kliktahu metadata cek <METADATA.md>`) dipakai tools/render_lokal.sh sebagai GERBANG:
render ditolak bila METADATA.md belum lengkap/valid (aturan keras: metadata lengkap SEBELUM render).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import ROOT, teks
from . import kanal as kanal_mod
from .meta import deskripsi as D
from .meta import hashtag as H
from .meta import judul as J
from .meta import tag as T
from .tema import BENCANA, TEMA

TAG_MAKS_KARAKTER = 60  # batas aman per tag (frasa long-tail <= ~8 kata); total tetap <= 500 cara YouTube
PENASARAN = ("ternyata", "padahal", "rahasia", "jarang", "kenapa", "apakah", "bagaimana", "misteri", "jawaban")
UMPAN_BOHONG = ("100%", "dijamin", "pasti terbukti", "terbukti mutlak", "dokter kaget", "wajib tonton", "viral banget")
TEMPLAT = {
    "tanya": [
        "{F}? Ini Jawaban Sainsnya",
        "{F}? Ternyata Ini Penyebabnya",
        "{F}? Jawabannya Tidak Seperti Dugaanmu",
        "{F}? Begini Penjelasan Ilmiahnya",
    ],
    "inti": [
        "Fakta {I} yang Jarang Diketahui",
        "Rahasia di Balik {I} yang Bikin Kaget",
    ],
    "misteri": ["Misteri {I} Akhirnya Terjawab"],  # hanya pilar misteri (jujur: bukan untuk topik yang tidak misterius)
    "shorts": ["{F}? Ini Kata Sains"],
    "long": ["{F}? Penjelasan Lengkap dari Nol", "Semua Tentang {I}: Dari Nol Sampai Paham"],
    "momen": ["{M}: {F}?"],
}
# topik BENCANA (korban jiwa nyata): templat bernada sensasi dibuang, kata berikut GALAT di judul/deskripsi
TEMPLAT_SENSASI = {"Rahasia di Balik {I} yang Bikin Kaget", "{F}? Jawabannya Tidak Seperti Dugaanmu"}
KATA_SENSASI = ("seru", "bikin kaget", "ngeri", "mengerikan", "merinding", "heboh", "kiamat", "seram")


@dataclass
class Paket:
    format: str
    tema: str
    kata_kunci: str
    judul: list[str]
    deskripsi: str
    hashtag: list[str]
    tag: list[str]
    sumber: list[dict[str, Any]] = field(default_factory=list)
    skor_judul: list[float] = field(default_factory=list)
    galat: list[str] = field(default_factory=list)
    peringatan: list[str] = field(default_factory=list)
    final: bool = False

    @property
    def tag_karakter(self) -> int:
        return teks.panjang_tag_youtube(self.tag)

    @property
    def lulus(self) -> bool:
        return not self.galat

    def baris_db(self, topik_id: int | None, episode_id: int | None = None, run_id: int | None = None) -> dict:
        return {
            "topik_id": topik_id,
            "episode_id": episode_id,
            "run_id": run_id,
            "format": self.format,
            "kata_kunci": self.kata_kunci,
            "judul": self.judul,
            "judul_terpilih": self.judul[0] if self.judul else None,
            "deskripsi": self.deskripsi,
            "hashtag": self.hashtag,
            "tag": self.tag,
            "tag_karakter": self.tag_karakter,
            "sumber": self.sumber,
            "lint": self.galat + [f"peringatan: {p}" for p in self.peringatan],
            "lulus": self.lulus,
        }


def _bersih(s: str) -> str:
    """ASCII saja, tanpa tanda < > (ditolak YouTube)."""
    return re.sub(r"[<>]", "", teks.ascii_saja(str(s))).strip()


# ================================================================================================ bahan
KATA_KORBAN = J.KATA_KORBAN  # topik bencana: tidak dijadikan judul/tag (lihat meta/judul.py)
frasa_layak = J.frasa_layak
kata_kunci_utama = J.kata_kunci_utama


# ================================================================================================ judul
skor_judul = J.skor_judul
kandidat_judul = J.kandidat_judul
pilih_beragam = J.pilih_beragam
duplikat_judul = J.duplikat
_inti_judul = J._inti_judul
TAG_MAKS_KARAKTER = T.MAKS_KARAKTER_PER_TAG
PENASARAN = J.PENASARAN
UMPAN_BOHONG = J.UMPAN_BOHONG


# ================================================================================================ hashtag & tag
def buat_hashtag(tema: str, inti: str, format_: str, k: kanal_mod.Kanal) -> list[str]:
    return H.buat_hashtag(tema, inti, format_, k, blokir=k.aturan.blokir, sensitif=k.aturan.sensitif)[0]


def buat_tag(
    kata_kunci: str, inti: str, tema: str, frasa: Sequence[str], k: kanal_mod.Kanal, tambahan: Sequence[str] = ()
) -> list[str]:
    return T.buat_tag(kata_kunci, inti, tema, frasa, k, tambahan)[0]


# ================================================================================================ deskripsi
BAB_MIN_DETIK = D.BAB_MIN_DETIK
bab_dari_timeline = D.bab_dari_timeline
sumber_dari_konten = D.sumber_dari_konten


# ================================================================================================ rakit
def buat(
    tema: str,
    frasa: Sequence[str],
    format_: str = "shorts",
    k: kanal_mod.Kanal | None = None,
    kata_kunci: str | None = None,
    hook: str | None = None,
    pesaing_judul: Sequence[str] = (),
    sumber: Sequence[dict[str, Any]] = (),
    konten: dict[str, Any] | None = None,
    timeline: dict[str, Any] | None = None,
    momen: str | None = None,
    judul_tambahan: Sequence[str] = (),
    ringkas: str | None = None,
    final: bool = False,
    sudut: Sequence[str] = (),
    bukti: Sequence[Any] | None = None,
    tanggal_riset: str | None = None,
    status_sumber: str | None = None,
) -> Paket:
    """rakit satu Paket metadata. Tahap 7-10: judul (sudut + bukti), deskripsi (setia bukti + provenance),
    hashtag (relevan, aturan platform), tag (variasi pencarian nyata, batas 500 karakter)."""
    k = k or kanal_mod.muat()
    t = TEMA.get(tema)
    inti = t.inti if t else tema
    hormat = tema in BENCANA
    fr = frasa_layak(frasa, k, tema)
    if not kata_kunci and konten and konten.get("kata_kunci"):
        kata_kunci = str(konten["kata_kunci"])
    kk = teks.norm(kata_kunci) if kata_kunci else kata_kunci_utama(fr, inti)
    tetap = [_bersih(j) for j in (konten or {}).get("judul", []) if isinstance(j, str) and j.strip()]
    judul, skor, peringatan_judul = J.buat(
        fr, inti, format_, k, kk, pesaing_judul, momen, t.pilar if t else "", hormat, sudut, tetap, bukti
    )
    tagar, peringatan_tagar = H.buat_hashtag(tema, inti, format_, k, blokir=k.aturan.blokir, sensitif=k.aturan.sensitif)
    bab = bab_dari_timeline(konten, timeline) if konten and timeline else []
    src = list(sumber) or (sumber_dari_konten(konten) if konten else [])
    desk = D.buat_deskripsi(
        kk,
        inti,
        tema,
        format_,
        k,
        hook,
        ringkas,
        bab,
        src,
        tagar,
        tanggal_riset,
        status_sumber,
        pilar=t.pilar if t else None,
    )
    tag, peringatan_tag = T.buat_tag(kk, inti, tema, fr, k, hashtag=tagar)
    p = Paket(format_, tema, kk, judul, desk, tagar, tag, src, skor)
    p.final = final
    g, w = lint(p, k, final=final, pilar=t.pilar if t else None)
    p.galat, p.peringatan = g, [*peringatan_judul, *peringatan_tagar, *peringatan_tag, *w]
    return p


# ================================================================================================ lint
def lint(p: Paket, k: kanal_mod.Kanal, final: bool = True, pilar: str | None = None) -> tuple[list[str], list[str]]:
    g: list[str] = []
    w: list[str] = []
    if len(p.judul) != 3:
        g.append(f"harus 3 pilihan judul (ada {len(p.judul)})")
    for i, j in enumerate(p.judul, 1):
        if not j.isascii():
            g.append(f"judul {i} tidak ASCII")
        if len(j) > k.metadata.maks_judul:
            g.append(f"judul {i} > {k.metadata.maks_judul} karakter")
        if re.search(r"[<>]", j):
            g.append(f"judul {i} memuat < atau > (ditolak YouTube)")
        if teks.diblokir(j, k.aturan.blokir):
            g.append(f"judul {i} memuat topik DIBLOKIR")
        if teks.sensitif(j, k.aturan.sensitif):
            g.append(f"judul {i} memuat kata sensitif")
        ideal = k.metadata.ideal_judul_shorts if p.format == "shorts" else k.metadata.ideal_judul_long
        if len(j) > ideal:
            w.append(f"judul {i} {len(j)} karakter (> ideal {ideal}, bisa terpotong di HP)")
    g += lint_deskripsi(p.deskripsi, p.format, k, final, pilar, p.judul[0] if p.judul else "")
    if p.tema in BENCANA:
        for nama, isi in [*[(f"judul {i}", j) for i, j in enumerate(p.judul, 1)], ("deskripsi", p.deskripsi)]:
            kena = [x for x in KATA_SENSASI if re.search(rf"(?<![0-9a-z]){x}(?![0-9a-z])", teks.norm(isi))]
            if kena:
                g.append(f"{nama}: topik bencana tidak boleh bernada sensasi ({', '.join(kena)})")
    g += lint_hashtag(p.hashtag, p.format, k, w)
    g += lint_tag(p.tag, k)
    return g, w


def lint_deskripsi(d: str, format_: str, k: kanal_mod.Kanal, final: bool, pilar: str | None, judul1: str) -> list[str]:
    return D.lint_deskripsi(d, format_, k, final, pilar, judul1)


def _detik(s: str) -> int:
    return D._detik(s)


def lint_hashtag(
    h: Sequence[str], format_: str, k: kanal_mod.Kanal, w: list[str], konteks: Sequence[str] = ()
) -> list[str]:
    return H.lint(h, format_, k, w, konteks)


def lint_tag(tag: Sequence[str], k: kanal_mod.Kanal) -> list[str]:
    return T.lint(tag, k)


# ================================================================================================ berkas MD
def tulis_md(p: Paket, path: Path | str, judul_halaman: str, catatan: str = "") -> Path:
    path = Path(path)
    status = "LULUS" if p.lulus else "GAGAL: " + "; ".join(p.galat)
    isi = [
        f"# METADATA - {_bersih(judul_halaman)}",
        "",
        f'> Dibuat oleh kliktahu/metadata.py. Format {p.format}. Kata kunci utama: "{p.kata_kunci}". '
        f"Lint {'final' if p.final else 'draf (lint final butuh bab dari timeline.json)'}: {status}."
        f"{(' ' + _bersih(catatan)) if catatan else ''}",
        "",
        "## 1. Judul (3 pilihan)",
        *[f"{i}. {j}" for i, j in enumerate(p.judul, 1)],
        "",
        "## 2. Deskripsi",
        "```text",
        p.deskripsi.rstrip("\n"),
        "```",
        "",
        "## 3. Hashtag",
        " ".join(p.hashtag),
        "",
        f"## 4. Tag ({p.tag_karakter}/500 karakter hitungan YouTube)",
        ", ".join(p.tag),
        "",
    ]
    if p.peringatan:
        isi += ["<!-- peringatan: " + " | ".join(_bersih(x) for x in p.peringatan) + " -->", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(isi), encoding="ascii", errors="strict")
    return path


def urai_md(s: str) -> dict[str, Any]:
    bag = {m.group(1): m.start() for m in re.finditer(r"(?m)^## ([1-4])\.", s)}
    if set(bag) != {"1", "2", "3", "4"}:
        raise ValueError(
            "METADATA.md harus punya 4 blok: '## 1. Judul', '## 2. Deskripsi', '## 3. Hashtag', '## 4. Tag'"
        )
    urut = sorted(bag.items(), key=lambda kv: kv[1])
    blok = {}
    for i, (n, a) in enumerate(urut):
        b = urut[i + 1][1] if i + 1 < len(urut) else len(s)
        blok[n] = s[a:b].split("\n", 1)[1] if "\n" in s[a:b] else ""
    judul = [re.sub(r"^\d\.\s*", "", ln).strip() for ln in blok["1"].splitlines() if re.match(r"^\d\.\s", ln)]
    m = re.search(r"```[a-z]*\n(.*?)```", blok["2"], re.S)
    desk = m.group(1) if m else blok["2"].strip()
    hashtag = re.findall(r"#\S+", re.sub(r"<!--.*?-->", "", blok["3"], flags=re.S))
    tag_txt = " ".join(ln for ln in re.sub(r"<!--.*?-->", "", blok["4"], flags=re.S).splitlines() if ln.strip())
    tag = [t.strip() for t in tag_txt.split(",") if t.strip()]
    return {"judul": judul, "deskripsi": desk, "hashtag": hashtag, "tag": tag}


def cek_md(
    path: Path | str,
    format_: str = "shorts",
    pilar: str | None = None,
    k: kanal_mod.Kanal | None = None,
    tema: str | None = None,
) -> tuple[list[str], list[str]]:
    """lint METADATA.md. Tema (bila tidak diberikan) dibaca dari content.json di folder yang sama -> pilar ikut
    diturunkan, sehingga gerbang render juga menegakkan disclaimer kesehatan & nada hormat topik bencana."""
    k = k or kanal_mod.muat()
    if tema is None:
        kj = Path(path).with_name("content.json")
        try:
            tema = json.loads(kj.read_text(encoding="utf-8")).get("topik") if kj.exists() else None
        except (ValueError, AttributeError):
            tema = None
    if tema in TEMA and not pilar:
        pilar = TEMA[tema].pilar
    raw = Path(path).read_bytes()
    try:
        s = raw.decode("ascii")
    except UnicodeDecodeError:
        return [f"{path}: berkas tidak ASCII (aturan METADATA)"], []
    try:
        d = urai_md(s)
    except ValueError as e:
        return [str(e)], []
    p = Paket(format_, tema if tema in TEMA else "", "", d["judul"], d["deskripsi"], d["hashtag"], d["tag"])
    return lint(p, k, final=True, pilar=pilar)


def tulis_siap_tempel(p: Paket, path: Path | str, kode: str, k: kanal_mod.Kanal, jam: str | None = None) -> Path:
    path = Path(path)
    isi = [
        f"# SIAP TEMPEL - {kode}",
        "",
        "Salin apa adanya ke YouTube Studio.",
        "",
        "## Judul (terpilih)",
        p.judul[0] if p.judul else "-",
        "",
        "## Deskripsi",
        "```text",
        p.deskripsi.rstrip("\n"),
        "```",
        "",
        "## Tag",
        ", ".join(p.tag),
        "",
        "## Komentar sematan",
        _bersih(
            f"Kenali jalur evakuasi di sekitarmu dan bagikan video ini ke keluarga. Info resmi & peringatan dini: "
            f"{BENCANA[p.tema]}."
            if p.tema in BENCANA
            else k.metadata.komentar_sematan
        ),
        "",
        "## Jam unggah (WIB)",
        jam or " atau ".join(k.jadwal.slot_wib),
        "",
        "## Judul cadangan",
        *[f"- {j}" for j in p.judul[1:]],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(isi), encoding="ascii", errors="strict")
    return path


def muat_json(p: Path) -> dict[str, Any] | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def konteks_episode(slug: str, format_: str) -> tuple[dict[str, Any], dict[str, Any] | None, Path]:
    """(content.json, timeline.json | None, folder episode)."""
    d = ROOT / ("episodes" if format_ == "shorts" else "long") / slug
    konten = muat_json(d / "content.json")
    if konten is None:
        raise FileNotFoundError(f"{d}/content.json tidak ada")
    tl = muat_json(ROOT / "build" / (slug if format_ == "shorts" else f"long/{slug}") / "timeline.json")
    return konten, tl, d
