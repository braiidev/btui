import pytest

from btui import cli, devices, known
from btui.cli import _direct


def test_parse_devices() -> None:
    text = "Device AA:BB:CC:DD:EE:FF Mi Telefono\nDevice 11:22:33:44:55:66\n"
    out = devices.parse_devices(text)
    assert out == [
        {"mac": "AA:BB:CC:DD:EE:FF", "name": "Mi Telefono"},
        {"mac": "11:22:33:44:55:66", "name": ""},
    ]


def test_known_roundtrip(tmp_path) -> None:
    known.add_known("AA:BB:CC:DD:EE:FF", "Telefono", cfg=tmp_path)
    known.add_known("11:22:33:44:55:66", "Pc", trusted=False, cfg=tmp_path)
    devs = known.load(tmp_path)
    assert len(devs) == 2
    assert devs[0]["mac"] == "AA:BB:CC:DD:EE:FF"
    assert devs[0]["trusted"] is True
    assert known.remove_known("AA:BB:CC:DD:EE:FF", cfg=tmp_path) is True
    assert [d["mac"] for d in known.load(tmp_path)] == ["11:22:33:44:55:66"]


def test_known_archivo_corrupto_devuelve_vacio(tmp_path) -> None:
    (tmp_path / "devices.json").write_text("{not json")
    assert known.load(tmp_path) == []


def test_devices_list_imprime_conocidos(tmp_path, capsys, monkeypatch) -> None:
    known.add_known("AA:BB", "A", cfg=tmp_path)
    monkeypatch.setattr(known, "config_dir", lambda: tmp_path)
    assert devices.run_cli("list", None) == 0
    assert "AA:BB\tA\ttrusted" in capsys.readouterr().out


def test_cli_devices_search_escalates(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda cmd: calls.append(cmd) or 0)
    monkeypatch.setattr(cli, "_is_root", lambda: False)
    assert cli.run(["--devices", "search"]) == 0
    assert calls[-1] == ["sudo", cli.BIN_PATH, "--devices", "search"]


def test_direct_devices_pair_root_es_local(monkeypatch):
    from pathlib import Path

    import tempfile

    results = []
    monkeypatch.setattr(
        devices,
        "_run",
        lambda *a: results.append(a) or type("P", (), {"returncode": 0})(),
    )
    monkeypatch.setattr(devices, "device_name", lambda _m: "X")
    monkeypatch.setattr(known, "config_dir", lambda: Path(tempfile.gettempdir()))
    assert _direct(["--devices", "pair", "AA:BB"]) == 0
    assert results[0] == ("bluetoothctl", "pair", "AA:BB")
    assert results[1] == ("bluetoothctl", "trust", "AA:BB")
