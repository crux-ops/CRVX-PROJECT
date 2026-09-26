"""Pemeriksa versi diuji tanpa jaringan dan tanpa mengubah berkas pin."""

from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest

from tools import cek_versi as V

NOW = dt.datetime(2026, 9, 26, tzinfo=dt.UTC)


def berkas(python=">=3.11", tanggal="2026-09-25T00:00:00Z", yanked=False):
    return {"requires_python": python, "upload_time_iso_8601": tanggal, "yanked": yanked}


def test_pilih_stabil_kompatibel_bukan_yanked_atau_masa_depan():
    data = {
        "releases": {
            "1.0": [berkas()],
            "1.1": [berkas()],
            "2.0": [berkas(python=">=3.12")],
            "3.0rc1": [berkas()],
            "4.0": [berkas(yanked=True)],
            "5.0": [berkas(tanggal="2026-10-01T00:00:00Z")],
            "6.0": [],
            "7.0": [berkas(python=None)],
            "invalid": [berkas()],
        }
    }
    assert V.pilih_rilis(data, "3.11.0", NOW) == "1.1"
    assert V.pilih_rilis(data, "3.14.0", NOW) == "2.0"


def test_tanggal_dan_metadata_rusak_tidak_diterima():
    data = {"releases": {"1.0": [berkas(tanggal="bad")], "2.0": [berkas(python="bad")]}}
    assert V.pilih_rilis(data, "3.11.0", NOW) is None
    with pytest.raises(ValueError, match="releases"):
        V.pilih_rilis({}, "3.11.0", NOW)


def test_marker_python_dan_pin_dari_pyproject(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[project]\ndependencies = ["numpy==1.0; python_version < \'3.12\'", '
        '"numpy==2.0; python_version >= \'3.12\'"]\n'
        '[project.optional-dependencies]\ndev = ["pytest==1.0"]\n',
        encoding="utf-8",
    )
    assert V.baca_pin(path, "3.11.0") == [("numpy", "1.0"), ("pytest", "1.0")]
    assert V.baca_pin(path, "3.14.0") == [("numpy", "2.0"), ("pytest", "1.0")]


def test_tolak_dependency_tanpa_pin(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\ndependencies = ["demo>=1"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="pin"):
        V.baca_pin(path, "3.11.0")


def test_fetch_hanya_pypi_dan_status_error():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"releases": {"1.0": [berkas()]}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        data = V.ambil_pypi(client, "Demo_Package")
    assert "releases" in data
    assert seen == ["https://pypi.org/pypi/demo-package/json"]
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            V.ambil_pypi(client, "demo")


def test_cli_laporan_tidak_mengubah_pin(tmp_path, monkeypatch, capsys):
    path = tmp_path / "pyproject.toml"
    isi = '[project]\ndependencies = ["demo==1.0"]\n'
    path.write_text(isi, encoding="utf-8")
    monkeypatch.setattr(V, "ambil_pypi", lambda *_: {"releases": {"1.0": [berkas()], "1.1": [berkas()]}})
    assert V.main(["--project", str(path), "--python-version", "3.11", "--as-of", "2026-09-25"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["hasil"][0]["terbaru_kompatibel"] == "1.1"
    assert output["hasil"][0]["status"] == "pembaruan_tersedia"
    assert path.read_text(encoding="utf-8") == isi


def test_cli_kegagalan_sumber_bukan_dianggap_terbaru(tmp_path, monkeypatch, capsys):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\ndependencies = ["demo==1.0"]\n', encoding="utf-8")

    def gagal(*_):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(V, "ambil_pypi", gagal)
    assert V.main(["--project", str(path), "--python-version", "3.11"]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["hasil"][0]["status"] == "gagal_verifikasi"


def test_cli_pin_tidak_tersedia(tmp_path, monkeypatch, capsys):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\ndependencies = ["demo==9.0"]\n', encoding="utf-8")
    monkeypatch.setattr(V, "ambil_pypi", lambda *_: {"releases": {"1.0": [berkas()]}})
    assert V.main(["--project", str(path), "--python-version", "3.11"]) == 2
    assert json.loads(capsys.readouterr().out)["hasil"][0]["status"] == "pin_tidak_terverifikasi"
