"""kliktahu/riset/agen.py - DATA AGEN: hasil web search / fetch agen AI (dipakai saat internet sandbox diblokir).

Agen mengambil data nyata dengan alatnya sendiri (web_search/fetch_page), menulisnya ke JSON dengan format di
bawah, lalu mesin memprosesnya PERSIS seperti data online (rumus sama, snapshot tersimpan, sumber dicatat).

{
  "diambil": "2026-09-25T15:00:00+07:00",
  "alat": "fetch_page + web_search agen Arena",
  "saran":   {"google": {"kenapa pelangi": ["kenapa pelangi melengkung", ...]}, "youtube": {...}},
  "wiki":    {"pelangi": {"judul": "Pelangi", "bulanan": {"2026-07": 1069, "2026-08": 1112, "2026-09": 629},
                          "hari_bulan_ini": 24}}                      (atau langsung {"views60": .., "tren": ..})
  "berita":  {"pelangi": {"n7": 3, "n28": 9}}                          (jumlah berita 7 & 28 hari terakhir)
  "tren_harian": [{"judul": "australia vs brasil", "traffic": 50000}],
  "pesaing": {"pelangi": {"jumlah": 18, "umur_median_hari": 400, "median_views": 52000, "rasio_outlier": 1.8,
                          "judul": ["..."]}},
  "momen_live": [{"tanggal": "2026-09-25", "nama": "...", "tema": ["gempa bumi"], "urgensi": 0.6, "sumber": "BMKG"}],
  "sumber_ilmiah": {"pelangi": [{"judul": "...", "url": "https://...", "penerbit": "NOAA", "tahun": 2023}]},
  "tanya":   {"pelangi": ["pertanyaan orang (People also ask / forum)", ...]}
}
Semua bagian opsional; tema tanpa data saran TIDAK diperingkat (bukan dianggap nol).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .. import teks
from ..momen import Momen
from ..tema import TEMA
from .sumber import wiki_dari_bulanan

BAGIAN = {
    "diambil",
    "alat",
    "saran",
    "wiki",
    "berita",
    "tren_harian",
    "pesaing",
    "momen_live",
    "sumber_ilmiah",
    "tanya",
    "_catatan",
}


class DataAgenError(ValueError):
    pass


def muat(path: Path | str) -> dict[str, Any]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise DataAgenError("data agen harus objek JSON")
    asing = set(d) - BAGIAN
    if asing:
        raise DataAgenError(f"bagian tidak dikenal di data agen: {sorted(asing)}")
    for k in ("wiki", "berita", "pesaing", "sumber_ilmiah", "tanya"):
        for tema in d.get(k, {}):
            if tema not in TEMA:
                raise DataAgenError(f"[{k}] tema '{tema}' tidak ada di registri tema (kliktahu/tema.py)")
    return d


class SumberAgen:
    """penyedia data untuk mesin dari berkas agen."""

    mode = "agen"

    def __init__(self, data: dict[str, Any], hari_ini: dt.date) -> None:
        self.d = data
        self.hari_ini = hari_ini
        self.diambil = data.get("diambil", "")

    def saran(self, q: str, sumber: str) -> list[str] | None:
        s = self.d.get("saran", {}).get(sumber, {})
        return list(s[q]) if q in s else None

    def punya_saran(self, tema: str) -> bool:
        t = TEMA[tema]
        qs = {teks.norm(q) for sm in self.d.get("saran", {}).values() for q in sm}
        return any(
            teks.norm(f"{b} {k}") in qs
            for b in ("kenapa", "apakah", "bagaimana", "padahal", "tiba-tiba")
            for k in t.kata
        )

    def wiki(self, tema: str) -> dict | None:
        w = self.d.get("wiki", {}).get(tema)
        if not w:
            return None
        if "views60" in w:
            return {
                "judul": w.get("judul", tema),
                "views60": float(w["views60"]),
                "tren": float(w.get("tren", 1.0)),
                "lonjakan_z": float(w.get("lonjakan_z", 0.0)),
            }
        return {
            "judul": w.get("judul", tema),
            **wiki_dari_bulanan(w.get("bulanan", {}), int(w.get("hari_bulan_ini", 30))),
        }

    def berita(self, tema: str) -> dict | None:
        b = self.d.get("berita", {}).get(tema)
        if not b:
            return None
        n7, n28 = float(b.get("n7", 0)), float(b.get("n28", b.get("n7", 0)))
        return {"n7": n7, "n28": n28, "rasio": round(n7 / max(0.5, (n28 - n7) / 3.0), 3), "judul": b.get("judul", [])}

    def tren(self) -> list[dict] | None:
        t = self.d.get("tren_harian")
        return list(t) if t is not None else None

    def pesaing(self, tema: str) -> dict | None:
        return self.d.get("pesaing", {}).get(tema)

    def momen_live(self) -> tuple[list[Momen], list[str]]:
        out = []
        for m in self.d.get("momen_live", []):
            out.append(
                Momen(
                    dt.date.fromisoformat(m["tanggal"]),
                    m["nama"],
                    list(m["tema"]),
                    "agen",
                    m.get("sumber", "agen"),
                    float(m.get("urgensi", 0.5)),
                )
            )
        return out, []

    def sumber_ilmiah(self, tema: str) -> list[dict] | None:
        s = self.d.get("sumber_ilmiah", {}).get(tema)
        if s is None:
            return None
        return [{"jenis": x.get("jenis", "lembaga"), "kredibel": bool(x.get("kredibel", True)), **x} for x in s]

    def tanya(self, tema: str) -> list[str]:
        return list(self.d.get("tanya", {}).get(tema, []))

    def pesaing_tersedia(self) -> bool:
        return bool(self.d.get("pesaing"))
