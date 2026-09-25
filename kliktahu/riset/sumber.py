"""kliktahu/riset/sumber.py - SUMBER DATA real-time. Tiap sumber = fungsi ambil (HTTP) + fungsi urai MURNI (teruji
dengan fixture). Galat jaringan -> Offline (mesin turun ke data lain); format berubah -> hasil kosong, bukan crash.

Tanpa kunci : Google & YouTube Autocomplete, Wikipedia (pencarian + pageview REST Wikimedia), Google News RSS,
              GDELT DOC 2.0, Google Trends harian (RSS), BMKG gempa, USGS, NOAA SWPC (Kp), JPL CAD, NASA EONET,
              OpenAlex, Europe PMC
Dengan kunci (env, opsional): YouTube Data API v3 (YOUTUBE_API_KEY), Brave Search (BRAVE_API_KEY),
              SearXNG milik sendiri (SEARXNG_URL)
"""

from __future__ import annotations

import datetime as dt
import email.utils
import json
import math
import re
import statistics
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote, urlparse

from ..momen import Momen
from .http import KlienRiset

UTC = dt.UTC
WIB = dt.timezone(dt.timedelta(hours=7))


def _json(teks: str) -> Any:
    teks = teks.strip()
    m = re.match(r"^[\w.$]+\((.*)\)\s*;?$", teks, re.S)  # JSONP window.google.ac.h([...])
    return json.loads(m.group(1) if m else teks)


# ================================================================================================ autocomplete
URL_SARAN = "https://suggestqueries.google.com/complete/search"


def urai_saran(teks: str) -> list[str]:
    try:
        data = _json(teks)
    except (ValueError, TypeError):
        return []
    daftar = data[1] if isinstance(data, list) and len(data) > 1 else []
    out = []
    for s in daftar:
        if isinstance(s, list) and s:  # format client=youtube: [["frasa", 0, [...]], ...]
            s = s[0]
        if isinstance(s, str) and s.strip():
            out.append(s.strip())
    return out[:10]


def saran(k: KlienRiset, q: str, sumber: str = "google") -> list[str]:
    p = {"client": "firefox", "hl": k.kanal.riset.hl, "gl": k.kanal.riset.gl, "ie": "utf-8", "oe": "utf-8", "q": q}
    if sumber == "youtube":
        p["ds"] = "yt"
    return urai_saran(k.get(URL_SARAN, p).teks)


# ================================================================================================ Wikipedia
def urai_opensearch(teks: str) -> str | None:
    try:
        d = json.loads(teks)
        return d[1][0] if d[1] else None
    except (ValueError, IndexError, TypeError):
        return None


def wiki_judul(k: KlienRiset, q: str, bahasa: str = "id") -> str | None:
    r = k.get(
        f"https://{bahasa}.wikipedia.org/w/api.php",
        {"action": "opensearch", "search": q, "limit": "1", "namespace": "0", "format": "json"},
        ttl_jam=168,
    )
    return urai_opensearch(r.teks)


PSEUDO = 100.0  # pseudo-count penyusut tren pageview (Bayes sederhana)


def hitung_wiki(harian: list[int]) -> dict[str, float]:
    """pageview harian (lama -> baru) -> views60, tren (30 terakhir / 30 sebelumnya), lonjakan_z (7 hari vs dasar)."""
    h = [max(0, int(x)) for x in harian][-60:]
    if not h:
        return {"views60": 0.0, "tren": 1.0, "lonjakan_z": 0.0}
    akhir, awal = h[-30:], h[:-30]
    tren = (
        ((sum(akhir) + PSEUDO) / (sum(awal) + PSEUDO)) if awal else 1.0
    )  # disusutkan: artikel sepi tidak melonjak palsu
    dasar, baru = h[:-7], h[-7:]
    z = 0.0
    if len(dasar) >= 14:
        mu = statistics.fmean(dasar)
        sd = statistics.pstdev(dasar) or 1.0
        z = (statistics.fmean(baru) - mu) / max(sd, mu * 0.1, 1.0)
    return {"views60": float(sum(h)), "tren": round(min(tren, 10.0), 4), "lonjakan_z": round(max(-6.0, min(6.0, z)), 3)}


def urai_pageview(teks: str) -> list[int]:
    try:
        return [int(it["views"]) for it in json.loads(teks).get("items", [])]
    except (ValueError, KeyError, TypeError):
        return []


def wiki_views(k: KlienRiset, judul: str, hari_ini: dt.date, bahasa: str = "id", hari: int = 60) -> dict | None:
    akhir = hari_ini - dt.timedelta(days=1)
    mulai = akhir - dt.timedelta(days=hari - 1)
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{bahasa}.wikipedia/all-access/user/"
        f"{quote(judul.replace(' ', '_'), safe='')}/daily/{mulai:%Y%m%d}/{akhir:%Y%m%d}"
    )
    r = k.get(url, ttl_jam=24, terima_404=True)
    if r.status == 404:
        return None
    h = urai_pageview(r.teks)
    return {"judul": judul, "bahasa": bahasa, **hitung_wiki(h), "hari": len(h)} if h else None


def wiki_dari_bulanan(bulanan: dict[str, int], hari_bulan_ini: int) -> dict[str, float]:
    """perkiraan views60/tren dari pageview BULANAN (data agen: endpoint monthly lebih ringkas).
    lonjakan_z = PROKSI dari tren bulanan ((tren - 1) x 3, dijepit +-6) karena data harian tidak tersedia."""
    kunci = sorted(bulanan)
    if not kunci:
        return {"views60": 0.0, "tren": 1.0, "lonjakan_z": 0.0}
    ini = bulanan[kunci[-1]]
    lalu = bulanan[kunci[-2]] if len(kunci) > 1 else ini
    lalu2 = bulanan[kunci[-3]] if len(kunci) > 2 else lalu
    if hari_bulan_ini >= 10:
        akhir30, awal30 = ini * 30.0 / hari_bulan_ini, float(lalu)
    else:
        akhir30, awal30 = float(lalu), float(lalu2)
    tren = (akhir30 + PSEUDO) / (awal30 + PSEUDO)  # 21 -> 75 tayangan bukan lonjakan nyata
    return {
        "views60": round(akhir30 + awal30, 1),
        "tren": round(tren, 4),
        "lonjakan_z": round(max(-6.0, min(6.0, (tren - 1.0) * 3.0)), 3),
    }


# ================================================================================================ berita
def _tgl_rss(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = email.utils.parsedate_to_datetime(s)
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def urai_rss(teks: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(teks)
    except ET.ParseError:
        return []
    out = []
    for it in root.iter("item"):
        src = it.find("source")
        t = _tgl_rss(it.findtext("pubDate"))
        out.append(
            {
                "judul": (it.findtext("title") or "").strip(),
                "url": (it.findtext("link") or "").strip(),
                "terbit": t.isoformat() if t else None,
                "sumber": (src.text or "").strip() if src is not None else "",
            }
        )
    return out


def hitung_berita(items: list[dict[str, Any]], sekarang: dt.datetime) -> dict[str, float]:
    """n7 = berita 7 hari terakhir; rasio = n7 / rata-rata mingguan 3 minggu sebelumnya (momentum berita)."""
    n7 = n_sbl = 0
    for it in items:
        if not it.get("terbit"):
            continue
        umur = (sekarang - dt.datetime.fromisoformat(it["terbit"])).total_seconds() / 86400
        if 0 <= umur <= 7:
            n7 += 1
        elif 7 < umur <= 28:
            n_sbl += 1
    return {"n7": float(n7), "n28": float(n7 + n_sbl), "rasio": round(n7 / max(0.5, n_sbl / 3.0), 3)}


def berita(k: KlienRiset, q: str, sekarang: dt.datetime) -> dict[str, Any]:
    r = k.get(
        "https://news.google.com/rss/search", {"q": f"{q} when:28d", "hl": "id", "gl": "ID", "ceid": "ID:id"}, ttl_jam=6
    )
    items = urai_rss(r.teks)
    return {**hitung_berita(items, sekarang), "judul": [i["judul"] for i in items[:8]]}


def urai_gdelt(teks: str) -> list[float]:
    try:
        tl = json.loads(teks).get("timeline", [])
        return [float(p.get("value", 0)) for p in (tl[0].get("data", []) if tl else [])]
    except (ValueError, AttributeError, TypeError):
        return []


def gdelt(k: KlienRiset, q: str) -> dict[str, float] | None:
    r = k.get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        {"query": f'"{q}" sourcelang:indonesian', "mode": "timelinevolraw", "timespan": "28d", "format": "json"},
        ttl_jam=6,
    )
    v = urai_gdelt(r.teks)
    if len(v) < 14:
        return None
    a, b = sum(v[-7:]), sum(v[:-7]) / max(1, (len(v) - 7) / 7)
    return {"n7": a, "rasio": round(a / max(0.5, b), 3)}


# ================================================================================================ Google Trends
def angka_traffic(s: str) -> int:
    s = (s or "").strip().upper().replace("+", "").replace(",", "").replace(".", "")
    mult = 1
    if s.endswith("K") or s.endswith("RB"):
        mult, s = 1000, s.rstrip("KRB")
    elif s.endswith("M") or s.endswith("JT"):
        mult, s = 1_000_000, s.rstrip("MJT")
    return int(s) * mult if s.isdigit() else 0


def urai_tren(teks: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(teks)
    except ET.ParseError:
        return []
    out = []
    for it in root.iter("item"):
        d: dict[str, Any] = {"judul": (it.findtext("title") or "").strip(), "traffic": 0, "berita": []}
        for el in it.iter():
            tag = el.tag.split("}")[-1]
            if tag == "approx_traffic":
                d["traffic"] = angka_traffic(el.text or "")
            elif tag == "news_item_title" and el.text:
                d["berita"].append(el.text.strip())
        t = _tgl_rss(it.findtext("pubDate"))
        d["terbit"] = t.isoformat() if t else None
        out.append(d)
    return out


def tren_harian(k: KlienRiset, geo: str = "ID") -> list[dict[str, Any]]:
    return urai_tren(k.get("https://trends.google.com/trending/rss", {"geo": geo}, ttl_jam=2).teks)


# ================================================================================================ YouTube Data API
YT_API = "https://www.googleapis.com/youtube/v3"


def durasi_iso(s: str) -> float:
    m = re.match(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", s or "")
    if not m:
        return 0.0
    d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    return float(d * 86400 + h * 3600 + mi * 60 + se)


def hitung_pesaing(video: list[dict[str, Any]], hari_ini: dt.date) -> dict[str, Any]:
    """video: {judul, views, terbit(ISO), subs, durasi}. -> ringkasan kejenuhan untuk skor_celah & outlier."""
    if not video:
        return {"jumlah": 0, "umur_median_hari": 730.0, "median_views": 0.0, "rasio_outlier": None, "judul": []}
    umur = [max(1.0, (hari_ini - dt.date.fromisoformat(v["terbit"][:10])).days) for v in video]
    views = [float(v.get("views") or 0) for v in video]
    rasio = [float(v["views"]) / max(100.0, float(v["subs"])) for v in video if v.get("subs")]
    return {
        "jumlah": sum(1 for x in views if x >= 10_000),
        "umur_median_hari": float(statistics.median(umur)),
        "median_views": float(statistics.median(views)),
        "views_per_hari_median": round(float(statistics.median(x / u for x, u in zip(views, umur))), 1),
        "rasio_outlier": round(float(statistics.median(rasio)), 3) if rasio else None,
        "durasi_median": float(statistics.median([v.get("durasi") or 0 for v in video])),
        "judul": [v["judul"] for v in sorted(video, key=lambda v: -float(v.get("views") or 0))[:12]],
    }


def youtube_pesaing(
    k: KlienRiset, q: str, key: str, hari_ini: dt.date, durasi: str = "short", maks: int = 25
) -> dict[str, Any]:
    """search.list (100 unit kuota) + videos.list (1) + channels.list (1)."""
    p = {
        "part": "snippet",
        "q": q,
        "type": "video",
        "maxResults": str(maks),
        "regionCode": "ID",
        "relevanceLanguage": "id",
        "order": "relevance",
        "key": key,
        "publishedAfter": f"{hari_ini - dt.timedelta(days=365)}T00:00:00Z",
    }
    if durasi != "any":
        p["videoDuration"] = durasi
    s = k.get(f"{YT_API}/search", p, ttl_jam=24).json()
    ids = [it["id"]["videoId"] for it in s.get("items", []) if it.get("id", {}).get("videoId")]
    if not ids:
        return hitung_pesaing([], hari_ini)
    v = k.get(
        f"{YT_API}/videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids), "key": key}, ttl_jam=24
    ).json()
    ch_ids = sorted({it["snippet"]["channelId"] for it in v.get("items", [])})
    ch = k.get(f"{YT_API}/channels", {"part": "statistics", "id": ",".join(ch_ids[:50]), "key": key}, ttl_jam=72).json()
    subs = {c["id"]: int(c.get("statistics", {}).get("subscriberCount") or 0) for c in ch.get("items", [])}
    video = [
        {
            "judul": it["snippet"]["title"],
            "views": int(it.get("statistics", {}).get("viewCount") or 0),
            "terbit": it["snippet"]["publishedAt"],
            "subs": subs.get(it["snippet"]["channelId"]),
            "durasi": durasi_iso(it.get("contentDetails", {}).get("duration", "")),
        }
        for it in v.get("items", [])
    ]
    return hitung_pesaing(video, hari_ini)


# ================================================================================================ momen live
def urai_bmkg(teks: str, hari_ini: dt.date) -> list[Momen]:
    try:
        g = json.loads(teks)["Infogempa"]["gempa"]
    except (ValueError, KeyError, TypeError):
        return []
    out = []
    for e in g if isinstance(g, list) else [g]:
        try:
            t = dt.datetime.fromisoformat(e["DateTime"].replace("Z", "+00:00")).astimezone(WIB)
            mag = float(e["Magnitude"])
        except (KeyError, ValueError):
            continue
        if (hari_ini - t.date()).days > 3:
            continue
        potensi = (e.get("Potensi") or "").lower()
        tsunami = "berpotensi tsunami" in potensi and "tidak" not in potensi
        urg = 1.0 if mag >= 7 or tsunami else 0.8 if mag >= 6 else 0.5 if (mag >= 5.5 or e.get("Dirasakan")) else 0.3
        out.append(
            Momen(
                t.date(),
                f"Gempa M{mag:.1f} {e.get('Wilayah', '').strip()} ({t:%d-%m %H.%M} WIB)",
                ["gempa bumi"] + (["tsunami"] if tsunami else []),
                "live",
                "BMKG (data.bmkg.go.id)",
                urg,
                lokasi=e.get("Wilayah"),
            )
        )
    return out


def momen_bmkg(k: KlienRiset, hari_ini: dt.date) -> list[Momen]:
    out = []
    for f in ("autogempa.json", "gempaterkini.json"):
        out += urai_bmkg(k.get(f"https://data.bmkg.go.id/DataMKG/TEWS/{f}", ttl_jam=0.5).teks, hari_ini)
    return out


def urai_usgs(teks: str, hari_ini: dt.date) -> list[Momen]:
    try:
        fs = json.loads(teks)["features"]
    except (ValueError, KeyError, TypeError):
        return []
    out = []
    for f in fs:
        p = f.get("properties", {})
        mag, tempat = float(p.get("mag") or 0), p.get("place") or ""
        t = dt.datetime.fromtimestamp((p.get("time") or 0) / 1000, UTC).astimezone(WIB)
        if (hari_ini - t.date()).days > 3 or mag < 6:
            continue
        indo = "indonesia" in tempat.lower()
        urg = (1.0 if mag >= 7 else 0.8) if indo else (0.6 if mag >= 7.5 else 0.3)
        out.append(
            Momen(
                t.date(),
                f"Gempa M{mag:.1f} {tempat}",
                ["gempa bumi"] + (["tsunami"] if p.get("tsunami") else []),
                "live",
                "USGS",
                urg,
                lokasi=tempat,
            )
        )
    return out


def urai_swpc(teks: str, hari_ini: dt.date) -> list[Momen]:
    try:
        d = json.loads(teks)
    except ValueError:
        return []
    baris: list[tuple[str, float]] = []
    if d and isinstance(d[0], list):  # format lama: baris pertama = header
        kol = d[0]
        for r in d[1:]:
            rec = dict(zip(kol, r))
            baris.append((str(rec.get("time_tag", "")), float(rec.get("kp") or 0)))
    else:
        for rec in d:
            baris.append((str(rec.get("time_tag", "")), float(rec.get("kp") or rec.get("Kp") or 0)))
    maks: dict[dt.date, float] = {}
    for tt, kp in baris:
        try:
            tg = dt.date.fromisoformat(tt[:10])
        except ValueError:
            continue
        if 0 <= (tg - hari_ini).days <= 3:
            maks[tg] = max(maks.get(tg, 0.0), kp)
    out = []
    for tg, kp in sorted(maks.items()):
        if kp >= 6:
            skala = "G4-G5" if kp >= 8 else "G3" if kp >= 7 else "G2"
            out.append(
                Momen(
                    tg,
                    f"Badai geomagnetik {skala} diprediksi (Kp {kp:.1f}) - aurora meluas",
                    ["aurora", "matahari"],
                    "live",
                    "NOAA SWPC",
                    1.0 if kp >= 8 else 0.9 if kp >= 7 else 0.5,
                )
            )
    return out


def urai_jpl(teks: str) -> list[Momen]:
    try:
        d = json.loads(teks)
        kol = d["fields"]
    except (ValueError, KeyError, TypeError):
        return []
    out = []
    for r in d.get("data", []):
        rec = dict(zip(kol, r))
        try:
            ld = float(rec["dist"]) * 389.17
            t = dt.datetime.strptime(rec["cd"], "%Y-%b-%d %H:%M").replace(tzinfo=UTC).astimezone(WIB)
        except (KeyError, ValueError):
            continue
        if ld > 5:
            continue
        out.append(
            Momen(
                t.date(),
                f"Asteroid {rec.get('des')} lewat {ld:.2f} jarak Bumi-Bulan",
                ["asteroid"],
                "live",
                "NASA JPL CNEOS",
                0.8 if ld < 1 else 0.5 if ld < 2 else 0.3,
            )
        )
    return out


def urai_eonet(teks: str) -> list[Momen]:
    try:
        ev = json.loads(teks)["events"]
    except (ValueError, KeyError, TypeError):
        return []
    peta = {"volcanoes": ["gunung berapi"], "severeStorms": ["angin & badai"], "earthquakes": ["gempa bumi"]}
    out = []
    for e in ev:
        kat = [c.get("id") for c in e.get("categories", [])]
        tema = [t for c in kat for t in peta.get(c or "", [])]
        if not tema or not e.get("geometry"):
            continue
        try:
            t = dt.datetime.fromisoformat(e["geometry"][-1]["date"].replace("Z", "+00:00")).astimezone(WIB)
        except (KeyError, ValueError):
            continue
        indo = "indonesia" in (e.get("title") or "").lower()
        out.append(
            Momen(
                t.date(),
                e.get("title", "Peristiwa alam"),
                tema,
                "live",
                "NASA EONET",
                0.8 if indo else 0.35,
                lokasi=e.get("title"),
            )
        )
    return out


def momen_live(k: KlienRiset, hari_ini: dt.date) -> tuple[list[Momen], list[str]]:
    """semua umpan live; sumber yang gagal dicatat, tidak menghentikan yang lain."""
    tugas = {
        "bmkg": lambda: momen_bmkg(k, hari_ini),
        "usgs": lambda: urai_usgs(
            k.get(
                "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson", ttl_jam=0.5
            ).teks,
            hari_ini,
        ),
        "swpc": lambda: urai_swpc(
            k.get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json", ttl_jam=1).teks,
            hari_ini,
        ),
        "jpl": lambda: urai_jpl(
            k.get(
                "https://ssd-api.jpl.nasa.gov/cad.api",
                {"date-min": "now", "date-max": "+30", "dist-max": "0.02"},
                ttl_jam=12,
            ).teks
        ),
        "eonet": lambda: urai_eonet(
            k.get("https://eonet.gsfc.nasa.gov/api/v3/events", {"status": "open", "days": "7"}, ttl_jam=3).teks
        ),
    }
    hasil = k.banyak(tugas)
    out, gagal = [], []
    for nama, h in sorted(hasil.items()):
        if isinstance(h, Exception):
            gagal.append(f"{nama}: {h}")
        else:
            out += h
    return out, gagal


# ================================================================================================ sumber kredibel
def kredibel(url: str, domain: tuple[str, ...] | list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domain)


def urai_openalex(teks: str) -> list[dict[str, Any]]:
    try:
        res = json.loads(teks).get("results", [])
    except ValueError:
        return []
    out = []
    for w in res:
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        loc = w.get("primary_location") or {}
        url = f"https://doi.org/{doi}" if doi else (loc.get("landing_page_url") or w.get("id"))
        if not url or not (w.get("display_name") or w.get("title")):
            continue
        out.append(
            {
                "judul": w.get("display_name") or w.get("title"),
                "url": url,
                "doi": doi,
                "penerbit": ((loc.get("source") or {}).get("display_name")),
                "tahun": w.get("publication_year"),
                "jenis": "jurnal",
                "kredibel": True,
                "kutipan": w.get("cited_by_count"),
            }
        )
    return out


def openalex(k: KlienRiset, q_en: str, maks: int = 5) -> list[dict[str, Any]]:
    p = {
        "search": q_en,
        "filter": "has_abstract:true,type:article",
        "sort": "cited_by_count:desc",
        "per-page": str(maks),
    }
    mail = k.kanal.riset.rahasia(k.kanal.riset.env_openalex_mailto)
    if mail:
        p["mailto"] = mail
    return urai_openalex(k.get("https://api.openalex.org/works", p, ttl_jam=168).teks)


def urai_europepmc(teks: str) -> list[dict[str, Any]]:
    try:
        res = json.loads(teks).get("resultList", {}).get("result", [])
    except ValueError:
        return []
    out = []
    for r in res:
        doi = r.get("doi")
        url = (
            f"https://doi.org/{doi}"
            if doi
            else (f"https://europepmc.org/article/MED/{r['pmid']}" if r.get("pmid") else None)
        )
        if url and r.get("title"):
            out.append(
                {
                    "judul": r["title"].rstrip("."),
                    "url": url,
                    "doi": doi,
                    "penerbit": r.get("journalTitle"),
                    "tahun": int(r["pubYear"]) if str(r.get("pubYear", "")).isdigit() else None,
                    "jenis": "jurnal",
                    "kredibel": True,
                    "kutipan": r.get("citedByCount"),
                }
            )
    return out


def europepmc(k: KlienRiset, q_en: str, maks: int = 5) -> list[dict[str, Any]]:
    return urai_europepmc(
        k.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            {"query": q_en, "format": "json", "pageSize": str(maks), "resultType": "lite", "sort": "CITED desc"},
            ttl_jam=168,
        ).teks
    )


# ================================================================================================ web search
def urai_brave(teks: str) -> dict[str, list[dict[str, str]]]:
    try:
        d = json.loads(teks)
    except ValueError:
        return {"hasil": [], "tanya": []}
    hasil = [
        {
            "judul": r.get("title", ""),
            "url": r.get("url", ""),
            "cuplik": re.sub(r"<[^>]+>", "", r.get("description", "")),
        }
        for r in d.get("web", {}).get("results", [])
    ]
    tanya = [{"tanya": r.get("question", ""), "url": r.get("url", "")} for r in d.get("faq", {}).get("results", [])]
    return {"hasil": hasil, "tanya": tanya}


def brave(k: KlienRiset, q: str, key: str) -> dict[str, list[dict[str, str]]]:
    return urai_brave(
        k.get(
            "https://api.search.brave.com/res/v1/web/search",
            {"q": q, "country": "id", "search_lang": "id", "count": "10"},
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            ttl_jam=24,
        ).teks
    )


def urai_searxng(teks: str) -> dict[str, list[dict[str, str]]]:
    try:
        d = json.loads(teks)
    except ValueError:
        return {"hasil": [], "tanya": []}
    return {
        "hasil": [
            {"judul": r.get("title", ""), "url": r.get("url", ""), "cuplik": r.get("content", "")}
            for r in d.get("results", [])
        ],
        "tanya": [],
    }


def searxng(k: KlienRiset, base: str, q: str) -> dict[str, list[dict[str, str]]]:
    return urai_searxng(
        k.get(base.rstrip("/") + "/search", {"q": q, "format": "json", "language": "id"}, ttl_jam=24).teks
    )


def web_cari(k: KlienRiset, q: str) -> dict[str, list[dict[str, str]]] | None:
    """web search umum bila kunci/URL tersedia (Brave atau SearXNG); None bila tidak dikonfigurasi."""
    r = k.kanal.riset
    key, base = r.rahasia(r.env_brave_key), r.rahasia(r.env_searxng_url)
    if key:
        return brave(k, q, key)
    if base:
        return searxng(k, base, q)
    return None


def skala_log(x: float, penuh: float) -> float:
    """0..1 logaritmik: x = penuh -> 1."""
    return 0.0 if x <= 1 else min(1.0, math.log10(x) / math.log10(penuh))
