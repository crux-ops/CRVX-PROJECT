"""kliktahu/sinkron.py - KLIEN Bolt Database / Supabase (PostgREST) untuk cermin/cadangan data di awan. OPSIONAL.

Bolt Database = Postgres gaya Supabase (REST PostgREST + RLS). Skema: skema/postgres.sql atau
supabase/migrations/*.sql. Lokal (SQLite) tetap SUMBER KEBENARAN; awan = cermin (id sama, upsert per id).

Konfigurasi HANYA lewat variabel lingkungan (tidak pernah di file/chat):
  URL : KLIKTAHU_SUPABASE_URL | SUPABASE_URL | VITE_SUPABASE_URL | BOLT_DATABASE_URL
  KEY : KLIKTAHU_SUPABASE_KEY | SUPABASE_SERVICE_ROLE_KEY | SUPABASE_KEY   (kunci layanan; RLS menolak anon)
Pakai:  python3 -m kliktahu sinkron cek | dorong | tarik
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from typing import Any

import httpx

from . import skema
from .db import DB

ENV_URL = ("KLIKTAHU_SUPABASE_URL", "SUPABASE_URL", "VITE_SUPABASE_URL", "BOLT_DATABASE_URL")
ENV_KEY = ("KLIKTAHU_SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY")
# urutan aman foreign key (induk dulu)
URUTAN = (
    "topik",
    "run_riset",
    "episode",
    "momen",
    "metadata",
    "snapshot_pencarian",
    "skor",
    "performa",
    "sumber_ilmiah",
    "rencana",
)
assert set(URUTAN) == set(skema.T), "URUTAN sinkron harus memuat semua tabel skema"


class SinkronError(RuntimeError):
    pass


def dari_env() -> tuple[str, str] | None:
    url = next((os.environ[k].strip() for k in ENV_URL if os.environ.get(k, "").strip()), "")
    key = next((os.environ[k].strip() for k in ENV_KEY if os.environ.get(k, "").strip()), "")
    return (url.rstrip("/"), key) if url and key else None


class KlienBolt:
    def __init__(
        self,
        url: str,
        key: str,
        transport: httpx.BaseTransport | None = None,
        batch: int = 500,
        percobaan: int = 3,
        tidur: Any = time.sleep,
    ) -> None:
        if not url.startswith("https://") and not url.startswith("http://localhost"):
            raise SinkronError("URL Bolt/Supabase harus https://")
        self.url = url.rstrip("/")
        self.batch = batch
        self.percobaan = percobaan
        self._tidur = tidur
        self._c = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "KlikTahuSinkron/2.0",
            },
        )

    def _minta(self, metode: str, path: str, **kw: Any) -> httpx.Response:
        for i in range(self.percobaan):
            try:
                r = self._c.request(metode, f"{self.url}{path}", **kw)
            except httpx.TransportError as e:
                if i == self.percobaan - 1:
                    raise SinkronError(f"tidak bisa menghubungi Bolt/Supabase: {e.__class__.__name__}") from e
                self._tidur(min(8.0, 0.5 * 2**i))
                continue
            if r.status_code in (429, 500, 502, 503, 504) and i < self.percobaan - 1:
                self._tidur(min(8.0, float(r.headers.get("retry-after", 0.5 * 2**i))))
                continue
            if r.status_code >= 400:
                raise SinkronError(f"{metode} {path} -> HTTP {r.status_code}: {r.text[:200]}")
            return r
        raise SinkronError("gagal setelah beberapa percobaan")  # pragma: no cover

    def cek(self) -> dict[str, Any]:
        """uji koneksi + tabel yang terlihat (butuh skema sudah dipasang)."""
        ada = {}
        for t in URUTAN:
            try:
                self._minta("GET", f"/rest/v1/{t}", params={"select": "id", "limit": "1"})
                ada[t] = True
            except SinkronError:
                ada[t] = False
        return {"url": self.url, "tabel": ada, "lengkap": all(ada.values())}

    def upsert(self, tabel: str, rows: Sequence[dict[str, Any]], on_conflict: str = "id") -> int:
        n = 0
        for i in range(0, len(rows), self.batch):
            bag = list(rows[i : i + self.batch])
            self._minta(
                "POST",
                f"/rest/v1/{tabel}",
                params={"on_conflict": on_conflict},
                json=bag,
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
            n += len(bag)
        return n

    def ambil(self, tabel: str, halaman: int = 1000) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        mulai = 0
        while True:
            r = self._minta(
                "GET",
                f"/rest/v1/{tabel}",
                params={"select": "*", "order": "id.asc", "limit": str(halaman), "offset": str(mulai)},
            )
            bag = r.json()
            out.extend(bag)
            if len(bag) < halaman:
                return out
            mulai += halaman

    def tutup(self) -> None:
        self._c.close()


def dorong(db: DB, klien: KlienBolt, tabel: Sequence[str] | None = None) -> dict[str, int]:
    """lokal -> awan (upsert per id, urutan foreign key)."""
    out = {}
    for t in URUTAN:
        if tabel and t not in tabel:
            continue
        out[t] = klien.upsert(t, db.daftar(t))
    return out


def tarik(db: DB, klien: KlienBolt, tabel: Sequence[str] | None = None) -> dict[str, int]:
    """awan -> lokal (upsert per id). Kolom asing diabaikan (awan boleh punya kolom tambahan)."""
    out = {}
    for t in URUTAN:
        if tabel and t not in tabel:
            continue
        kol = {c.nama for c in skema.T[t].kolom}
        n = 0
        for r in klien.ambil(t):
            db.upsert(t, {k: v for k, v in r.items() if k in kol}, ("id",))
            n += 1
        out[t] = n
    db.commit()
    return out
