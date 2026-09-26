"""pytest bersama: basis data sementara + satu run riset mode uji (dipakai beberapa tes)."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kliktahu import kanal  # noqa: E402
from kliktahu.db import DB  # noqa: E402

HARI = dt.date(2026, 9, 25)


@pytest.fixture()
def k() -> kanal.Kanal:
    return kanal.muat()


@pytest.fixture()
def db(tmp_path: Path) -> DB:
    d = DB(tmp_path / "t.db")
    yield d
    d.tutup()


@pytest.fixture(scope="session")
def riset_uji(tmp_path_factory: pytest.TempPathFactory):
    from kliktahu.riset import mesin

    tmp = tmp_path_factory.mktemp("riset")
    d = DB(tmp / "riset.db")
    h = mesin.jalankan("uji", HARI, db=d, folder_laporan=tmp / "lap", ekspor=False, log=lambda s: None)
    return h, d, tmp


@pytest.fixture()
def pencari_uji():
    """Pencari mode uji (transport palsu deterministik) untuk kliktahu/cari.py."""
    from kliktahu.cari import Pencari
    from kliktahu.riset.fixture import transport_uji
    from kliktahu.riset.http import KlienRiset

    k = kanal.muat()
    kl = KlienRiset(k, transport=transport_uji(HARI), pakai_cache=False, tidur=lambda s: None)
    return Pencari(kl, k, HARI, "uji")
