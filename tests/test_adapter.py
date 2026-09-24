import pytest

from btui import cli


@pytest.fixture
def capture(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda cmd: calls.append(cmd) or 0)
    return calls


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--name", "server-bt"], ["sudo", cli.BIN_PATH, "--name", "server-bt"]),
        (["--discoverable", "on"], ["sudo", cli.BIN_PATH, "--discoverable", "on"]),
        (
            ["--discoverable", "on", "--timeout", "180"],
            ["sudo", cli.BIN_PATH, "--discoverable", "on", "--timeout", "180"],
        ),
        (["--pairable", "off"], ["sudo", cli.BIN_PATH, "--pairable", "off"]),
    ],
)
def test_settings_escalate_via_sudo(capture, monkeypatch, argv, expected):
    monkeypatch.setattr(cli, "_is_root", lambda: False)
    assert cli.run(argv) == 0
    assert capture[-1] == expected


def test_discoverable_as_root_calls_bluetoothctl(monkeypatch):
    from btui import radio

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return type("P", (), {"returncode": 0, "stdout": "done", "stderr": ""})()

    monkeypatch.setattr(radio.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_is_root", lambda: True)

    assert cli.run(["--discoverable", "on", "--timeout", "180"]) == 0
    assert calls == [
        ["bluetoothctl", "discoverable", "on"],
        ["bluetoothctl", "discoverable-timeout", "180"],
    ]


def test_pairable_as_root_calls_bluetoothctl(monkeypatch):
    from btui import radio

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return type("P", (), {"returncode": 0, "stdout": "done", "stderr": ""})()

    monkeypatch.setattr(radio.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_is_root", lambda: True)

    assert cli.run(["--pairable", "on"]) == 0
    assert calls == [["bluetoothctl", "pairable", "on"]]


def test_name_as_root_sets_alias(monkeypatch):
    from btui import radio

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return type(
            "P",
            (),
            {"returncode": 0, "stdout": "SetSystemAlias complete", "stderr": ""},
        )()

    monkeypatch.setattr(radio.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "_is_root", lambda: True)

    assert cli.run(["--name", "miniserver"]) == 0
    assert calls == [["bluetoothctl", "system-alias", "miniserver"]]
