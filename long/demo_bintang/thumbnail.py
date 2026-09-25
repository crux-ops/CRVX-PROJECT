#!/usr/bin/env python3
"""thumbnail 1280x720 untuk demo_bintang -> build/long/demo_bintang/thumbnail.jpg"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "long"))
from PIL import Image  # noqa: E402

import diagrams as D  # noqa: E402
import mesin_fx as FX  # noqa: E402
import mesin_long as L  # noqa: E402
import mesin_v11 as V  # noqa: E402


def main():
    D.set_ss(1.0)
    ak = D.col("#FF6B3D")
    img = L.latar_default((1920, 1080), 20.0, None, ak)
    D.glow(img, 330, 700, 420, "#FFB020", 0.5)
    D.circ(img, 330, 700, 190, "#FFB020")
    D.circ(img, 270, 640, 80, D.terang("#FFB020", 0.5), 0.5)
    D.glow(img, 1650, 380, 200, "#FF5A3C", 0.6)
    D.circ(img, 1650, 380, 70, "#FF5A3C")
    for i in range(14):
        D.line(img, 560 + i * 70, 560 - i * 12, 590 + i * 70, 555 - i * 12, 8, D.PUTIH, 0.8)
    L.teks(img, "SEBERAPA JAUH", 1060, 250, 150, "B", D.PUTIH, 1, "ms", bayang=0.8)
    V.judul_kinetik(img, "BINTANG TERDEKAT?", 1060, 420, 120, 9.0, 0.0, ak, "TERDEKAT?", warna=D.PUTIH,
                    max_w=1500, max_h=150, maks_baris=1, warna_stabilo=D.gelap(ak, 0.1))
    V.stiker(img, "40 TRILIUN KM", 1300, 820, 9.0, 0.0, 78, ak, rot=-5, goyang=False)
    img = FX.finishing(img, "sinema", 0)
    out = ROOT / "build" / "long" / "demo_bintang" / "thumbnail.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.resize((1280, 720), Image.LANCZOS).save(out, quality=92)
    print(f"thumbnail -> {out}")


if __name__ == "__main__":
    main()
