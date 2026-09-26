"""Karakterisasi dan regresi HTTP; seluruh permintaan memakai MockTransport."""

from __future__ import annotations

from email.utils import formatdate

import httpx
import pytest

from kliktahu.riset import http as H


def klien(handler, tidur=None, cache=None):
    c = H.KlienRiset(
        transport=httpx.MockTransport(handler),
        pakai_cache=False,
        cache=cache,
        tidur=tidur if tidur is not None else lambda _: None,
    )
    c.jeda = 0
    return c


def test_karakterisasi_json_cache_dan_404():
    calls = []
    cache = H.Cache(":memory:")

    def handler(request):
        calls.append(request)
        return httpx.Response(404) if request.url.path == "/missing" else httpx.Response(200, json={"ok": True})

    c = klien(handler, cache=cache)
    try:
        assert c.get("https://example.org/data", ttl_jam=1).json() == {"ok": True}
        assert c.get("https://example.org/data", ttl_jam=1).dari_cache
        assert len(calls) == 1
        assert c.get("https://example.org/missing", terima_404=True).status == 404
    finally:
        c.tutup()
        cache._con.close()


def test_karakterisasi_retry_dan_error():
    statuses = iter([503, 200, 403])
    c = klien(lambda _: httpx.Response(next(statuses), text="ok"))
    try:
        assert c.get("https://example.org/data").teks == "ok"
        assert c.stat["coba_ulang"] == 1
        with pytest.raises(H.GagalHTTP) as exc:
            c.get("https://example.org/forbidden")
        assert exc.value.status == 403
    finally:
        c.tutup()


def test_url_aman_query_userinfo_fragment_dan_encoding():
    url = "https://user:password@example.org/data?%61pi_key=secret&q=a%26b#token=hidden"
    aman = H._url_aman(url, None)
    assert str(httpx.URL(aman)) == "https://example.org/data?q=a%26b"
    assert H._url_aman("https://example.org/data", {"q": "a&b", "KEY": "secret"}) == aman


def test_url_aman_mengikuti_semantik_params_httpx():
    url = "https://example.org/data?old=1&token=secret"
    params = {"q": ["a", "b"], "blank": "", "flag": True}
    expected = str(httpx.Request("GET", url, params=params).url)
    assert H._url_aman(url, params) == expected
    assert H._url_aman(url, {}) == str(httpx.Request("GET", url, params={}).url)


def test_rahasia_tidak_masuk_respon_cache_atau_error():
    cache = H.Cache(":memory:")
    c = klien(lambda _: httpx.Response(200, json={"ok": True}), cache=cache)
    try:
        r = c.get("https://example.org/data?api_key=secret&q=test", ttl_jam=1)
        assert "secret" not in r.url
        stored = cache._con.execute("SELECT url FROM http").fetchone()[0]
        assert "secret" not in stored
    finally:
        c.tutup()
        cache._con.close()
    c = klien(lambda _: httpx.Response(403))
    try:
        with pytest.raises(H.GagalHTTP) as exc:
            c.get("https://example.org/data?token=secret")
        assert "secret" not in str(exc.value)
    finally:
        c.tutup()


@pytest.mark.parametrize("header", ["12", "12.5", " 12 "])
def test_retry_after_angka(header):
    sleeps = []
    statuses = iter([429, 200])
    c = klien(lambda _: httpx.Response(next(statuses), headers={"Retry-After": header}), tidur=sleeps.append)
    try:
        assert c.get("https://example.org/data").status == 200
        assert sleeps == [float(header)]
    finally:
        c.tutup()


def test_retry_after_tanggal_http(monkeypatch):
    now = 1_800_000_000
    monkeypatch.setattr(H.time, "time", lambda: now)
    sleeps = []
    statuses = iter([503, 200])
    header = formatdate(now + 20, usegmt=True)
    c = klien(lambda _: httpx.Response(next(statuses), headers={"Retry-After": header}), tidur=sleeps.append)
    try:
        assert c.get("https://example.org/data").status == 200
        assert sleeps == [20.0]
    finally:
        c.tutup()


@pytest.mark.parametrize("header", ["31", "999999999999999999999999"])
def test_retry_after_panjang_tidak_dicoba_terlalu_cepat(header):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": header})

    c = klien(handler)
    try:
        with pytest.raises(H.GagalHTTP):
            c.get("https://example.org/data")
        assert len(calls) == 1
    finally:
        c.tutup()


@pytest.mark.parametrize("header", ["bad", "-2", "nan", "inf"])
def test_retry_after_invalid_memakai_backoff(header):
    sleeps = []
    statuses = iter([503, 200])
    c = klien(lambda _: httpx.Response(next(statuses), headers={"Retry-After": header}), tidur=sleeps.append)
    try:
        assert c.get("https://example.org/data").status == 200
        assert len(sleeps) == 1
        assert 0 <= sleeps[0] <= 0.6
    finally:
        c.tutup()
