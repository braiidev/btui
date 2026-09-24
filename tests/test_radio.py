import pytest

from btui import cli


@pytest.fixture
def capture(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda cmd: calls.append(cmd) or 0)
    return calls


def test_on_escalates_via_sudo(capture, monkeypatch):
    monkeypatch.setattr(cli, "_is_root", lambda: False)
    assert cli.run(["--on"]) == 0
    assert capture[-1] == ["sudo", cli.BIN_PATH, "--on"]


def test_off_as_root_toggles_radio(monkeypatch, capsys):
    from btui import radio

    calls = []

    fake_bluetoothctl = "changing power off\nsucceeded"

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return type(
            "P", (), {"returncode": 0, "stdout": fake_bluetoothctl, "stderr": ""}
        )()

    monkeypatch.setattr(radio.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_is_root", lambda: True)
    assert cli.run(["--off"]) == 0
    assert calls == [["bluetoothctl", "power", "off"]]
