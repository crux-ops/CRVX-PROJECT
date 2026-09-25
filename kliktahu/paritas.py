"""kliktahu/paritas.py - fixture PARITAS rumus skor Python <-> TypeScript (skema/ts/fixture/skor_paritas.json).

Masukan acak berbenih tetap (deterministik) + keluaran kliktahu/skor.py. Tes TypeScript (node --test) memanggil
port skema/ts/src/skor.ts dengan masukan yang sama dan harus memberi angka yang sama (toleransi 1e-9).
Ikut ditulis/dicek oleh `python3 -m kliktahu skema tulis|cek`, jadi port TS tidak bisa diam-diam melenceng.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from typing import Any, TypeVar

from . import skor as S

PILAR = ["tubuh", "antariksa", "bumi", "hewan", "teknologi", "misteri"]
T = TypeVar("T")


class Acak:
    """pembangkit acak STABIL lintas versi Python: hanya memakai random.random() (satu-satunya yang dijamin sama
    urutannya antar versi); randint/choice/sample bawaan boleh berubah antar versi (3.11 vs 3.14 berbeda)."""

    def __init__(self, benih: int) -> None:
        self._r = random.Random(benih)

    def random(self) -> float:
        return self._r.random()

    def randint(self, a: int, b: int) -> int:
        return a + int(self._r.random() * (b - a + 1))

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self._r.random()

    def choice(self, xs: Sequence[T]) -> T:
        return xs[int(self._r.random() * len(xs))]

    def sample(self, xs: Sequence[T], k: int) -> list[T]:
        kolam, out = list(xs), []
        for _ in range(k):
            out.append(kolam.pop(int(self._r.random() * len(kolam))))
        return out


def _sig(r: Acak) -> dict[str, float]:
    return {
        "jml": float(r.randint(0, 150)),
        "kuat": round(r.uniform(0, 90), 2),
        "niat": float(r.randint(0, 120)),
        "yt": float(r.randint(0, 90)),
        "sains": float(r.randint(0, 20)),
        "rel": float(r.randint(0, 40)),
        "kom": float(r.randint(0, 60)),
        "vis": round(r.uniform(0, 30), 2),
        "ever": float(r.randint(0, 1)),
    }


def _opsional(r: Acak, v: Any, p: float = 0.25) -> Any:
    return None if r.random() < p else v


def kasus(n: int = 40, benih: int = 20260925) -> list[dict[str, Any]]:
    r = Acak(benih)
    out: list[dict[str, Any]] = []

    def tambah(fn: str, masukan: list[Any], keluaran: Any) -> None:
        out.append({"fn": fn, "in": masukan, "out": keluaran})

    kata = [f"frasa {i}" for i in range(30)]
    for _ in range(n):
        s = _sig(r)
        tambah("v3_skor", [s], S.v3_skor(s))
        sk = _opsional(r, round(r.uniform(0, 400), 3), 0.5)
        tambah("v3_tumbuh", [s, sk], S.v3_tumbuh(s, sk))
        pos = [r.randint(0, 9) for _ in range(r.randint(0, 12))]
        tambah("kuat", [pos], S.kuat(pos))
        a = [round(r.uniform(0, 500), 3), r.randint(0, 10), round(r.uniform(0, 2), 2), r.randint(0, 30)]
        tambah("v4_keluarga", a, S.v4_keluarga(*a))
        f1 = r.sample(kata, r.randint(0, 20))
        f0 = _opsional(r, r.sample(kata, r.randint(0, 20)))
        j0 = None if f0 is None else float(r.randint(0, 150))
        tambah("v5_velocity", [float(len(f1)), f1, j0, f0], S.v5_velocity(float(len(f1)), f1, j0, f0))
        sisa = _opsional(r, r.randint(-10, 60), 0.15)
        tambah("v5_momen", [sisa, 45], S.v5_momen(sisa, 45))
        b: list[Any] = [s, r.randint(0, 10), round(r.uniform(-1, 2), 3), round(r.uniform(0, 1), 3)]
        tambah("v5_views", b, S.v5_views(*b))
        vals = [round(r.uniform(0, 600), 2) for _ in range(r.randint(0, 8))]
        tambah("norm01", [vals], S.norm01(vals))
        w = [float(r.choice([0, 1, 50, 900, 12000, 250000, 3000000])), round(r.uniform(0, 3), 3)]
        tambah("skor_wiki", w, S.skor_wiki(*w))
        c = [float(r.randint(0, 80)), float(r.randint(1, 2000)), float(r.randint(0, 2000000))]
        tambah("skor_celah", c, S.skor_celah(*c))
        rata = {p: round(r.uniform(0, 90000), 1) for p in r.sample(PILAR, r.randint(0, 6))}
        tambah("bobot_pilar", [rata, PILAR], S.bobot_pilar(rata, PILAR))
        v6 = [round(r.random(), 4) for _ in range(6)]
        tambah("v6_papan", v6, S.v6_papan(*v6))
        m = [
            _opsional(r, round(r.uniform(-2, 3), 3), 0.4),
            _opsional(r, round(r.uniform(0, 12), 3), 0.4),
            _opsional(r, float(r.choice([1, 200, 5000, 20000, 500000])), 0.6),
            _opsional(r, round(r.uniform(-6, 6), 3), 0.4),
        ]
        tambah("momentum", m, S.momentum(*m))
        cv = [_opsional(r, round(r.random(), 4), 0.3), _opsional(r, round(r.uniform(0.001, 300), 3), 0.4)]
        tambah("celah_v7", cv, S.celah_v7(*cv))
        kc: list[Any] = [round(r.random(), 4), round(r.random(), 4), float(r.randint(0, 1)), r.random() < 0.5]
        tambah("kecocokan", kc, S.kecocokan(*kc))
        ks: list[Any] = [r.choice(["segar", "long", "dibahas"]), round(r.random(), 4)]
        tambah("kesegaran", ks, S.kesegaran(*ks))
        bk = [_opsional(r, r.randint(0, 9), 0.3)]
        tambah("bukti", bk, S.bukti(*bk))
        kom = {nama: _opsional(r, [round(r.random(), 4), round(r.random(), 4)], 0.3) for nama in S.BOBOT_V7}
        tambah("v7_peluang", [kom], list(S.v7_peluang({k: tuple(v) if v else None for k, v in kom.items()})))
        fs = [r.randint(0, 9), round(r.uniform(0, 2), 2), float(r.randint(0, 1)), round(r.uniform(30, 90), 1)]
        tambah("format_saran", fs, S.format_saran(*fs))
    for i in range(24):  # komponen tidak dipakai kanal (analisis pesaing dimatikan pemilik)
        kom = {nama: _opsional(r, [round(r.random(), 4), round(r.random(), 4)], 0.3) for nama in S.BOBOT_V7}
        tanpa = ["celah"] if i % 3 else ["celah", "bukti"]
        hasil = S.v7_peluang({k: tuple(v) if v else None for k, v in kom.items()}, tanpa)
        tambah("v7_peluang", [kom, tanpa], list(hasil))
    return out


def fixture_json() -> str:
    d = {
        "_catatan": "DIHASILKAN OTOMATIS oleh kliktahu/paritas.py - JANGAN diedit manual.",
        "bobot_v7": S.BOBOT_V7,
        "kasus": kasus(),
    }
    return json.dumps(d, ensure_ascii=False, indent=None, separators=(",", ":")) + "\n"
