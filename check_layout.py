#!/usr/bin/env python3
"""check_layout.py <slug> [--sheet path] - audit tata letak/margin sebelum render.
Render tiap adegan di 3 titik waktu (SS 0.75, tanpa finishing), ukur tinta di zona margin aman + kotak teks tercatat.
HARUS bersih (exit 1 bila ada pelanggaran)."""
import sys
import render as R
import mesin_util as U


def main(slug, sheet="build/layout_check.jpg"):
    content, tl = R.setup(slug, 0.75, 0)
    bad_total = 0
    frames = []
    for s in tl["scenes"]:
        for f in (0.25, 0.6, 0.95):
            t = s["start"] + s["dur"] * f
            R.CTX["boxes"] = []
            img = R.render_frame(t, finishing=False)
            rep = U.ink_report(img, boxes=R.CTX["boxes"])
            frames.append((t, img))
            flag = "OK " if not rep["pelanggaran"] else "!! "
            print("%s %-10s t=%6.2f bawah %.1f%% kanan %.1f%% isi150-650 %.1f%% %s" % (
                flag, s["id"], t, rep["bawah_ui"] * 100, rep["kolom_kanan"] * 100, rep["isi_150_650"] * 100,
                "; ".join(rep["pelanggaran"])))
            bad_total += len(rep["pelanggaran"])
    R.CTX.pop("boxes", None)
    U.sheet(frames, sheet, cols=9, thumb_w=200)
    print("montase ->", sheet)
    print("LAYOUT BERSIH" if bad_total == 0 else "LAYOUT GAGAL: %d pelanggaran" % bad_total)
    return 0 if bad_total == 0 else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    sheet = a[a.index("--sheet") + 1] if "--sheet" in a else "build/layout_check.jpg"
    sys.exit(main(a[0], sheet))
