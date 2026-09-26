"""Audit pin PyPI, tanpa instalasi atau perubahan otomatis.

Jalankan di lingkungan requirements-dev.txt (packaging disediakan oleh pytest).
Exit 0: semua pin terverifikasi terbaru; 1: ada pembaruan; 2: verifikasi gagal.
Kompatibilitas di sini hanya Requires-Python, bukan jaminan wheel/ABI atau resolver.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

import httpx
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parent.parent


def baca_pin(path: Path, python: str) -> list[tuple[str, str]]:
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    environment = default_environment()
    environment["python_full_version"] = python
    environment["python_version"] = ".".join(python.split(".")[:2])
    environment["implementation_version"] = python
    requirements = project.get("dependencies", []) + project.get("optional-dependencies", {}).get("dev", [])
    hasil = []
    for text in requirements:
        req = Requirement(text)
        if req.marker and not req.marker.evaluate(environment):
            continue
        specs = list(req.specifier)
        if req.url or len(specs) != 1 or specs[0].operator != "==" or "*" in specs[0].version:
            raise ValueError(f"Perlu pin versi persis: {req.name}")
        hasil.append((canonicalize_name(req.name), specs[0].version))
    return hasil


def ambil_pypi(client: httpx.Client, nama: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", nama):
        raise ValueError("Nama paket tidak valid")
    response = client.get(f"https://pypi.org/pypi/{canonicalize_name(nama)}/json")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("releases"), dict):
        raise ValueError("Respons PyPI tidak memiliki releases")
    return data


def _berkas_kompatibel(file: Any, python: str, batas: dt.datetime) -> bool:
    if not isinstance(file, dict) or file.get("yanked", True) is not False:
        return False
    requires = file.get("requires_python")
    # Metadata yang hilang berarti belum terverifikasi, bukan otomatis kompatibel.
    if not isinstance(requires, str):
        return False
    try:
        timestamp = file["upload_time_iso_8601"]
        if not isinstance(timestamp, str):
            return False
        uploaded = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if uploaded.tzinfo is None or uploaded > batas:
            return False
        return SpecifierSet(requires).contains(python, prereleases=False)
    except (KeyError, TypeError, ValueError, InvalidSpecifier):
        return False


def pilih_rilis(data: dict[str, Any], python: str, batas: dt.datetime) -> str | None:
    releases = data.get("releases")
    if not isinstance(releases, dict):
        raise ValueError("Respons PyPI tidak memiliki releases")
    if batas.tzinfo is None:
        raise ValueError("Batas tanggal harus memiliki zona waktu")
    kandidat = []
    for nama, files in releases.items():
        try:
            version = Version(nama)
        except (InvalidVersion, TypeError):
            continue
        if version.is_prerelease or version.is_devrelease or version.local is not None:
            continue
        if isinstance(files, list) and any(_berkas_kompatibel(f, python, batas) for f in files):
            kandidat.append((version, nama))
    return max(kandidat)[1] if kandidat else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT / "pyproject.toml")
    parser.add_argument("--python-version", default=platform.python_version())
    parser.add_argument("--as-of", help="Tanggal UTC YYYY-MM-DD; tidak boleh di masa depan")
    args = parser.parse_args(argv)
    now = dt.datetime.now(dt.UTC)
    try:
        python = Version(args.python_version)
        if len(python.release) not in (2, 3) or python.is_prerelease or python.is_devrelease:
            raise ValueError("Gunakan versi Python stabil X.Y atau X.Y.Z")
        target = ".".join(str(x) for x in (*python.release, 0)[:3])
        batas = now
        if args.as_of:
            date = dt.date.fromisoformat(args.as_of)
            if date > now.date():
                raise ValueError("Tanggal verifikasi tidak boleh di masa depan")
            batas = min(now, dt.datetime.combine(date, dt.time.max, tzinfo=dt.UTC))
        pins = baca_pin(args.project, target)
        if not pins:
            raise ValueError("Tidak ada pin aktif untuk target Python")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Konfigurasi tidak valid: {exc}", file=sys.stderr)
        return 2
    hasil = []
    exit_code = 0
    with httpx.Client(
        timeout=20.0, follow_redirects=False, headers={"User-Agent": "KlikTahu-VersionAudit/1.0"}
    ) as client:
        for nama, pin in pins:
            row: dict[str, Any] = {"paket": nama, "pin": pin, "sumber": f"https://pypi.org/pypi/{nama}/json"}
            try:
                data = ambil_pypi(client, nama)
                terbaru = pilih_rilis(data, target, batas)
                files = data["releases"].get(pin, [])
                valid_pin = isinstance(files, list) and any(_berkas_kompatibel(f, target, batas) for f in files)
                row["terbaru_kompatibel"] = terbaru
                if not valid_pin or terbaru is None:
                    row["status"] = "pin_tidak_terverifikasi"
                    exit_code = 2
                elif Version(pin) < Version(terbaru):
                    row["status"] = "pembaruan_tersedia"
                    exit_code = max(exit_code, 1)
                elif Version(pin) == Version(terbaru):
                    row["status"] = "terverifikasi"
                else:
                    row["status"] = "pin_tidak_terverifikasi"
                    exit_code = 2
            except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                row["status"] = "gagal_verifikasi"
                row["galat"] = type(exc).__name__
                exit_code = 2
            hasil.append(row)
    print(
        json.dumps(
            {
                "diambil_utc": now.isoformat(),
                "batas_rilis_utc": batas.isoformat(),
                "python": target,
                "batasan": "Requires-Python saja; uji resolver, wheel, ABI, dan CI tetap wajib. Tidak mengubah pin.",
                "hasil": hasil,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
