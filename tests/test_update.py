from btui import update


def test_parse_version():
    assert update.parse_version("0.9") == (0, 9)
    assert update.parse_version("v0.10") == (0, 10)
    assert update.parse_version("0.5.1") == (0, 5, 1)
    assert update.parse_version("basura") is None


def test_parse_tags_extrae_y_deduplica():
    out = (
        "abc\trefs/tags/v0.8\n"
        "def\trefs/tags/v0.9\n"
        "ghi\trefs/tags/v0.9^{}\n"
        "jkl\trefs/heads/main\n"
    )
    assert update.parse_tags(out) == ["v0.8", "v0.9"]


def test_latest_elige_mayor_numericamente():
    assert update.latest(["v0.8", "v0.10", "v0.9"]) == "v0.10"
    assert update.latest(["basura", "v0.2"]) == "v0.2"
    assert update.latest(["basura"]) is None


def test_compare():
    assert update.compare("0.9", "0.10") == -1
    assert update.compare("0.10", "0.9") == 1
    assert update.compare("0.9", "v0.9") == 0


def test_run_al_dia(monkeypatch, capsys):
    class _Proc:
        returncode = 0
        stdout = "abc\trefs/tags/v0.9\n"

    monkeypatch.setattr(update.subprocess, "run", lambda *a, **k: _Proc())
    monkeypatch.setattr(update, "__version__", "0.9")
    assert update.run() == 0
    assert "al dia" in capsys.readouterr().out


def test_run_hay_nueva(monkeypatch, capsys):
    class _Proc:
        returncode = 0
        stdout = "abc\trefs/tags/v0.10\n"

    monkeypatch.setattr(update.subprocess, "run", lambda *a, **k: _Proc())
    monkeypatch.setattr(update, "__version__", "0.9")
    assert update.run() == 1
    assert "hay v0.10 disponible" in capsys.readouterr().out


def test_run_sin_git(monkeypatch, capsys):
    def boom(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(update.subprocess, "run", boom)
    assert update.run() == 2
    assert "git no esta disponible" in capsys.readouterr().err
