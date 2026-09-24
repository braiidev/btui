import pytest

from btui import cli


@pytest.fixture
def capture(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda cmd: calls.append(cmd) or 0)
    return calls


def test_install_escalates_via_sudo(capture, monkeypatch):
    monkeypatch.setattr(cli, "_is_root", lambda: False)
    assert cli.run(["--install"]) == 0
    assert capture[-1] == ["sudo", cli.BIN_PATH, "--install"]


def test_install_as_root_uses_install_sh(capture, monkeypatch):
    monkeypatch.setattr(cli, "_is_root", lambda: True)
    assert cli.run(["--install"]) == 0
    assert capture[-1] == ["sh", str(cli.REPO_ROOT / "install.sh"), "--install"]


def test_update_and_uninstall_route_to_script(capture, monkeypatch):
    monkeypatch.setattr(cli, "_is_root", lambda: True)
    cli.run(["--uninstall"])
    assert capture[-1] == ["sh", str(cli.REPO_ROOT / "install.sh"), "--uninstall"]


def test_service_actions_route_to_rc_service(capture, monkeypatch):
    monkeypatch.setattr(cli, "_is_root", lambda: True)
    cli.run(["--restart"])
    assert capture[-1] == ["rc-service", "btui", "restart"]
    cli.run(["--stop"])
    assert capture[-1] == ["rc-service", "btui", "stop"]


def test_info_routes(monkeypatch):
    calls = []
    monkeypatch.setattr("btui.info.run", lambda: calls.append("info") or 0)
    assert cli.run(["--info"]) == 0
    assert calls == ["info"]


def test_daemon_is_routed(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_daemon", lambda: calls.append("daemon") or 0)
    assert cli.run(["daemon"]) == 0
    assert calls == ["daemon"]


def test_daemon_placeholder_stops_on_signal(monkeypatch):
    invoked = {"signal": None}

    def fake_sleep(_secs):
        invoked["signal"](None, None)

    import signal

    monkeypatch.setattr(signal, "SIGTERM", 15)

    def fake_signal(signum, handler):
        invoked["signal"] = handler

    monkeypatch.setattr(signal, "signal", fake_signal)
    assert cli.run_daemon(sleep=fake_sleep) == 0