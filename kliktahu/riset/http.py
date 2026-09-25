"""kliktahu/riset/http.py - KLIEN HTTP riset yang SOPAN dan tangguh (httpx, HTTP/2).

* batas laju per host (jeda minimum + maksimal N permintaan bersamaan per host) - tidak membanjiri server
* coba ulang dengan backoff eksponensial + jitter penuh untuk 429/5xx/timeout; menghormati header Retry-After
* host yang tidak terjangkau (diblokir/offline) ditandai -> gagal cepat (Offline), mesin turun ke mode data lain
* cache SQLite (data/cache_http.sqlite, TTL dari kanal.toml) -> jalankan ulang tidak memukul server lagi
* transport bisa diganti (httpx.MockTransport) -> seluruh jalur HTTP diuji OFFLINE secara deterministik
Kunci API tidak pernah ikut kunci cache, log, atau snapshot.
"""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import random
import sqlite3
import threading
import time
import zlib
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .. import ROOT
from .. import kanal as kanal_mod

CACHE_BAWAAN = ROOT / "data" / "cache_http.sqlite"
_RAHASIA = {"key", "api_key", "apikey", "token", "access_token", "x-subscription-token", "authorization"}
try:  # HTTP/2 bila paket h2 terpasang (requirements: httpx[http2])
    import h2  # noqa: F401

    _H2 = True
except ImportError:  # pragma: no cover
    _H2 = False


class Offline(Exception):
    """sumber tidak terjangkau (internet mati / host diblokir / DNS gagal)."""


class GagalHTTP(Exception):
    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"HTTP {status}: {url}")
        self.status = status


@dataclass
class Respon:
    url: str
    status: int
    isi: bytes
    dari_cache: bool
    durasi_ms: int

    @property
    def teks(self) -> str:
        return self.isi.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.teks)


class Cache:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._con = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS http (kunci TEXT PRIMARY KEY, url TEXT, status INTEGER, diambil REAL, isi BLOB)"
        )
        self._con.commit()

    def ambil(self, kunci: str, ttl_detik: float) -> tuple[int, bytes] | None:
        with self._lock:
            r = self._con.execute("SELECT status, diambil, isi FROM http WHERE kunci = ?", (kunci,)).fetchone()
        if r and time.time() - r[1] <= ttl_detik:
            return int(r[0]), zlib.decompress(r[2])
        return None

    def simpan(self, kunci: str, url: str, status: int, isi: bytes) -> None:
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO http VALUES (?, ?, ?, ?, ?)",
                (kunci, url, status, time.time(), zlib.compress(isi, 6)),
            )
            self._con.commit()

    def bersihkan(self, umur_detik: float = 7 * 86400) -> int:
        with self._lock:
            n = self._con.execute("DELETE FROM http WHERE diambil < ?", (time.time() - umur_detik,)).rowcount
            self._con.commit()
        return int(n)


def _url_aman(url: str, params: Mapping[str, Any] | None) -> str:
    """URL untuk kunci cache/log TANPA parameter rahasia."""
    p = {k: v for k, v in sorted((params or {}).items()) if k.lower() not in _RAHASIA}
    return url + ("?" + "&".join(f"{k}={v}" for k, v in p.items()) if p else "")


class KlienRiset:
    def __init__(
        self,
        kanal: kanal_mod.Kanal | None = None,
        transport: httpx.BaseTransport | None = None,
        cache: Cache | None = None,
        pakai_cache: bool = True,
        tidur: Callable[[float], None] = time.sleep,
        jam: Callable[[], float] = time.monotonic,
        benih_acak: int = 0,
    ) -> None:
        self.kanal = kanal or kanal_mod.muat()
        r = self.kanal.riset
        self.ttl = r.cache_jam * 3600
        self.jeda = r.jeda_min_detik
        self.maks_paralel = r.maks_paralel
        self.cache = cache if cache is not None else (Cache(CACHE_BAWAAN) if pakai_cache else None)
        self._tidur, self._jam = tidur, jam
        self._acak = random.Random(benih_acak)
        self._c = httpx.Client(
            http2=_H2 and transport is None,
            transport=transport,
            follow_redirects=True,
            timeout=httpx.Timeout(15.0, connect=8.0),
            headers={"User-Agent": r.user_agent, "Accept-Language": "id-ID,id;q=0.9,en;q=0.7"},
        )
        self._kunci_host: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._berikut: dict[str, float] = defaultdict(float)
        self._sem: dict[str, threading.Semaphore] = defaultdict(lambda: threading.Semaphore(r.maks_paralel_per_host))
        self._lock = threading.Lock()
        self.stat: Counter[str] = Counter()
        self.host_mati: set[str] = set()
        self.log: list[str] = []

    # ------------------------------------------------------------------------------------ inti
    def _tunggu_giliran(self, host: str) -> None:
        with self._kunci_host[host]:
            now = self._jam()
            tunggu = max(0.0, self._berikut[host] - now)
            self._berikut[host] = max(now, self._berikut[host]) + self.jeda
        if tunggu > 0:
            self._tidur(tunggu)

    def _catat(self, k: str, n: int = 1) -> None:
        with self._lock:
            self.stat[k] += n

    def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        ttl_jam: float | None = None,
        percobaan: int = 4,
        terima_404: bool = False,
    ) -> Respon:
        aman = _url_aman(url, params)
        kunci = hashlib.sha1(aman.encode()).hexdigest()
        ttl = self.ttl if ttl_jam is None else ttl_jam * 3600
        if self.cache is not None and ttl > 0:
            c = self.cache.ambil(kunci, ttl)
            if c is not None:
                self._catat("cache")
                return Respon(aman, c[0], c[1], True, 0)
        host = urlparse(url).hostname or "?"
        if host in self.host_mati:
            self._catat("gagal_cepat")
            raise Offline(f"{host} tidak terjangkau")
        t0 = time.perf_counter()
        with self._sem[host]:
            for i in range(percobaan):
                self._tunggu_giliran(host)
                self._catat("permintaan")
                try:
                    r = self._c.get(url, params=params, headers=headers)
                except (httpx.ConnectError, httpx.UnsupportedProtocol) as e:
                    if i >= 1:  # 2x gagal sambung = anggap host mati (blokir/DNS) -> berhenti mencoba
                        with self._lock:
                            self.host_mati.add(host)
                        self._catat("offline")
                        self.log.append(f"OFFLINE {host}: {e.__class__.__name__}")
                        raise Offline(f"{host}: {e.__class__.__name__}") from e
                    self._tidur(self._backoff(i))
                    continue
                except httpx.TransportError as e:  # timeout baca, protokol putus
                    if i == percobaan - 1:
                        self._catat("gagal")
                        raise Offline(f"{host}: {e.__class__.__name__}") from e
                    self._catat("coba_ulang")
                    self._tidur(self._backoff(i))
                    continue
                if r.status_code in (429, 500, 502, 503, 504) and i < percobaan - 1:
                    self._catat("coba_ulang")
                    ra = r.headers.get("retry-after", "")
                    self._tidur(min(30.0, float(ra)) if ra.replace(".", "", 1).isdigit() else self._backoff(i))
                    continue
                dur = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 404 and terima_404:
                    return Respon(aman, 404, b"", False, dur)
                if r.status_code >= 400:
                    self._catat("gagal")
                    raise GagalHTTP(r.status_code, aman)
                if self.cache is not None and ttl > 0:
                    self.cache.simpan(kunci, aman, r.status_code, r.content)
                return Respon(aman, r.status_code, r.content, False, dur)
        raise Offline(f"{host}: gagal setelah {percobaan} percobaan")  # pragma: no cover

    def _backoff(self, i: int) -> float:
        """jitter penuh: acak 0..min(20, 0.6 * 2^i) detik."""
        return self._acak.uniform(0, min(20.0, 0.6 * 2**i))

    def banyak(self, tugas: Mapping[str, Callable[[], Any]]) -> dict[str, Any]:
        """jalankan banyak panggilan paralel (dibatasi maks_paralel + batas per host). Galat -> objek Exception."""
        out: dict[str, Any] = {}
        with cf.ThreadPoolExecutor(max_workers=self.maks_paralel) as ex:
            fut = {ex.submit(fn): k for k, fn in tugas.items()}
            for f in cf.as_completed(fut):
                k = fut[f]
                try:
                    out[k] = f.result()
                except Exception as e:
                    out[k] = e
        return out

    def tutup(self) -> None:
        self._c.close()
