"""kliktahu - lapisan DATA, RISET REAL-TIME, METADATA, PERENCANA, dan DASBOR untuk mesin produksi KlikTahu.

Mesin render (render.py, mesin_v11.py, long/...) TIDAK bergantung pada paket ini; paket ini hanya
membaca/menulis data (SQLite), meriset topik, dan menyiapkan metadata/rencana sebelum produksi.

Navigasi (CLI):  python3 -m kliktahu --help
"""

from __future__ import annotations

from pathlib import Path

__version__ = "2.0.0"
ROOT = Path(__file__).resolve().parent.parent
