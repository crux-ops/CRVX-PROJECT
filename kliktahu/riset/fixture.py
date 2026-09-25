"""kliktahu/riset/fixture.py - "INTERNET PALSU" deterministik untuk mode --uji (tanpa jaringan).

httpx.MockTransport yang menjawab SEMUA sumber riset dengan format ASLI masing-masing (JSON autocomplete, REST
Wikimedia, RSS Google News & Trends, JSON YouTube Data API, BMKG, USGS, NOAA, JPL, EONET, OpenAlex, Europe PMC,
Brave) sehingga seluruh jalur HTTP -> urai -> skor -> DB -> laporan teruji. Isi sengaja memuat frasa DIBLOKIR dan
SENSITIF agar penyaring ikut teruji. Sama persis setiap kali (benih crc32 dari URL).
"""

from __future__ import annotations

import datetime as dt
import json
import zlib
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from ..tema import DAFTAR, TEMA

_TMPL = [
    "{q} {a}",
    "{q} {a} menurut sains",
    "{q} terjadi",
    "{q} bisa {a}",
    "{q} saat malam",
    "{q} setiap hari",
    "{q} warna {a}",
    "{q} berbahaya atau tidak",
    "{q} pada anak",
    "{q} {a} fakta ilmiah",
]


def _rr(s: str) -> int:
    return zlib.crc32(s.encode())


def saran_palsu(q: str, ds: str) -> list[str]:
    rr = _rr(f"{ds}:{q}")
    kata = q.split(" ", 1)[1] if " " in q else q
    tema = next((t for t in DAFTAR if any(kata.startswith(x) or x.startswith(kata) for x in t.kata)), None)
    asp = list(tema.aspek) if tema else ["itu", "terjadi"]
    out = []
    for i in range(6 + rr % 4):
        a = asp[(rr >> (i + 1)) % len(asp)]
        out.append(_TMPL[(rr + i * 7) % len(_TMPL)].format(q=q, a=a))
    if rr % 5 == 0:
        out.insert(2, f"{q} kentut bau")  # WAJIB terbuang (blokir)
    if rr % 7 == 0:
        out.insert(4, f"{q} keringat dingin")  # WAJIB terbuang (blokir)
    if rr % 6 == 0:
        out.insert(3, f"{q} lambang lgbt")  # boleh di data, DILARANG di judul/tag (sensitif)
    return list(dict.fromkeys(out))[:10]


def _pageview(judul: str, mulai: dt.date, akhir: dt.date) -> dict:
    rr = _rr(judul)
    base = 40 + rr % 3000
    items, d, i = [], mulai, 0
    while d <= akhir:
        v = base + (rr >> (i % 16)) % max(1, base // 5)
        if judul in ("Hari_tanpa_bayangan", "Aurora") and (akhir - d).days < 7:
            v *= 4  # lonjakan 7 hari terakhir -> momentum
        items.append(
            {
                "project": "id.wikipedia",
                "article": judul,
                "granularity": "daily",
                "timestamp": d.strftime("%Y%m%d00"),
                "access": "all-access",
                "agent": "user",
                "views": int(v),
            }
        )
        d += dt.timedelta(days=1)
        i += 1
    return {"items": items}


def _rss_berita(q: str, sekarang: dt.datetime) -> str:
    rr = _rr(q)
    n = 3 + rr % 12
    item = []
    for i in range(n):
        t = sekarang - dt.timedelta(hours=(rr >> i) % 600 + i * 7)
        item.append(
            f"<item><title>Berita {q} ke-{i + 1} - Kompas</title><link>https://contoh.id/{i}</link>"
            f"<pubDate>{t.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>"
            f'<source url="https://contoh.id">Kompas</source></item>'
        )
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>{q}</title>{"".join(item)}</channel></rss>'


def _rss_tren(sekarang: dt.datetime) -> str:
    data = [
        ("australia vs brasil", "50000+"),
        ("hari tanpa bayangan", "20000+"),
        ("gempa hari ini", "10000+"),
        ("harga emas", "5000+"),
    ]
    item = "".join(
        f"<item><title>{j}</title><ht:approx_traffic>{t}</ht:approx_traffic>"
        f"<pubDate>{sekarang.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
        f"<ht:news_item><ht:news_item_title>Berita {j}</ht:news_item_title></ht:news_item></item>"
        for j, t in data
    )
    return (
        '<?xml version="1.0"?><rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">'
        f"<channel><title>Daily Search Trends</title>{item}</channel></rss>"
    )


def _yt_search(q: str) -> dict:
    rr = _rr(q)
    return {"items": [{"id": {"kind": "youtube#video", "videoId": f"v{rr % 997}_{i}"}} for i in range(8 + rr % 10)]}


def _yt_videos(ids: list[str], hari_ini: dt.date) -> dict:
    out = []
    for i, v in enumerate(ids):
        rr = _rr(v)
        terbit = hari_ini - dt.timedelta(days=5 + rr % 360)
        out.append(
            {
                "id": v,
                "snippet": {
                    "title": f"Kenapa fakta {v} bikin kaget #shorts",
                    "channelId": f"c{rr % 5}",
                    "publishedAt": f"{terbit}T10:00:00Z",
                },
                "statistics": {"viewCount": str(500 + (rr % 400000))},
                "contentDetails": {"duration": f"PT{rr % 2}M{10 + rr % 49}S"},
            }
        )
    return {"items": out}


def _yt_channels(ids: list[str]) -> dict:
    return {"items": [{"id": c, "statistics": {"subscriberCount": str(1000 + _rr(c) % 900000)}} for c in ids]}


def transport_uji(hari_ini: dt.date) -> httpx.MockTransport:
    sekarang = dt.datetime(hari_ini.year, hari_ini.month, hari_ini.day, 9, tzinfo=dt.UTC)
    kemarin = sekarang - dt.timedelta(hours=20)

    def jawab(req: httpx.Request) -> httpx.Response:
        u = urlparse(str(req.url))
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        h, p = u.hostname or "", u.path

        def js(obj: object) -> httpx.Response:
            return httpx.Response(200, content=json.dumps(obj).encode(), headers={"content-type": "application/json"})

        if h == "suggestqueries.google.com":
            return js([q["q"], saran_palsu(q["q"], q.get("ds", "g")), [], {}])
        if h.endswith("wikipedia.org") and p == "/w/api.php":
            t = next((t for t in DAFTAR if q.get("search", "").lower() in (t.nama, *t.kata)), None)
            return js([q.get("search"), [t.wiki.replace("_", " ")] if t else [], [""], [""]])
        if h == "wikimedia.org" and "/pageviews/per-article/" in p:
            bag = p.split("/")
            judul, mulai, akhir = unquote(bag[-4]), bag[-2], bag[-1]
            if judul not in {t.wiki for t in TEMA.values()}:
                return httpx.Response(404, content=b'{"type":"not_found"}')
            return js(
                _pageview(
                    judul, dt.datetime.strptime(mulai, "%Y%m%d").date(), dt.datetime.strptime(akhir, "%Y%m%d").date()
                )
            )
        if h == "news.google.com":
            return httpx.Response(200, content=_rss_berita(q.get("q", ""), sekarang).encode())
        if h == "api.gdeltproject.org":
            rr = _rr(q.get("query", ""))
            return js(
                {
                    "timeline": [
                        {
                            "series": "Volume",
                            "data": [{"date": f"d{i}", "value": (rr >> (i % 20)) % 30} for i in range(28)],
                        }
                    ]
                }
            )
        if h == "trends.google.com":
            return httpx.Response(200, content=_rss_tren(sekarang).encode())
        if h == "www.googleapis.com" and p.endswith("/search"):
            return js(_yt_search(q.get("q", "")))
        if h == "www.googleapis.com" and p.endswith("/videos"):
            return js(_yt_videos(q.get("id", "").split(","), hari_ini))
        if h == "www.googleapis.com" and p.endswith("/channels"):
            return js(_yt_channels(q.get("id", "").split(",")))
        if h == "data.bmkg.go.id":
            g = {
                "Tanggal": kemarin.strftime("%d %b %Y"),
                "Jam": "10:12:33 WIB",
                "DateTime": kemarin.isoformat(),
                "Magnitude": "5.9",
                "Kedalaman": "10 km",
                "Wilayah": "Pusat gempa di laut 80 km BaratDaya Sukabumi",
                "Potensi": "Tidak berpotensi tsunami",
                "Dirasakan": "III Sukabumi, II Bandung",
            }
            return js({"Infogempa": {"gempa": g if p.endswith("autogempa.json") else [g]}})
        if h == "earthquake.usgs.gov":
            return js(
                {
                    "features": [
                        {
                            "properties": {
                                "mag": 6.1,
                                "place": "80 km SW of Sukabumi, Indonesia",
                                "time": int(kemarin.timestamp() * 1000),
                                "tsunami": 0,
                            }
                        }
                    ]
                }
            )
        if h == "services.swpc.noaa.gov":
            rows: list[list[Any]] = [["time_tag", "kp", "observed", "noaa_scale"]]
            for i in range(24):
                tt = sekarang + dt.timedelta(hours=3 * i)
                rows.append([tt.strftime("%Y-%m-%d %H:%M:%S"), "5.33" if i == 9 else "2.67", "predicted", None])
            return js(rows)
        if h == "ssd-api.jpl.nasa.gov":
            cd = (sekarang + dt.timedelta(days=6)).strftime("%Y-%b-%d %H:%M")
            return js(
                {
                    "fields": [
                        "des",
                        "orbit_id",
                        "jd",
                        "cd",
                        "dist",
                        "dist_min",
                        "dist_max",
                        "v_rel",
                        "v_inf",
                        "t_sigma_f",
                        "h",
                    ],
                    "data": [
                        ["2026 SX1", "5", "2461318.5", cd, "0.004", "0.0039", "0.0041", "8.2", "8.1", "< 00:01", "26.1"]
                    ],
                }
            )
        if h == "eonet.gsfc.nasa.gov":
            return js(
                {
                    "events": [
                        {
                            "title": "Lewotobi Laki-laki Volcano, Indonesia",
                            "categories": [{"id": "volcanoes"}],
                            "geometry": [{"date": kemarin.strftime("%Y-%m-%dT%H:%M:%SZ")}],
                        }
                    ]
                }
            )
        if h == "api.openalex.org":
            s = q.get("search", "")
            return js(
                {
                    "results": [
                        {
                            "id": f"https://openalex.org/W{i}",
                            "display_name": f"A study of {s} ({i})",
                            "doi": f"https://doi.org/10.1000/{abs(_rr(s)) % 9999}.{i}",
                            "publication_year": 2020 + i,
                            "cited_by_count": 300 - i * 40,
                            "primary_location": {"source": {"display_name": "Nature"}},
                        }
                        for i in range(3)
                    ]
                }
            )
        if h == "www.ebi.ac.uk":
            s = q.get("query", "")
            return js(
                {
                    "resultList": {
                        "result": [
                            {
                                "title": f"Clinical review of {s}.",
                                "journalTitle": "BMJ",
                                "pubYear": "2022",
                                "doi": f"10.1136/{abs(_rr(s)) % 999}",
                                "citedByCount": 50,
                            }
                        ]
                    }
                }
            )
        if h == "api.search.brave.com":
            return js(
                {
                    "web": {
                        "results": [{"title": "NASA", "url": "https://science.nasa.gov/x", "description": "<b>x</b>"}]
                    },
                    "faq": {"results": [{"question": f"Apakah {q.get('q')} berbahaya?", "url": "https://contoh.id"}]},
                }
            )
        return httpx.Response(404, content=b"tidak ada fixture")

    return httpx.MockTransport(jawab)
