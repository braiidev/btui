from btui import tui


def test_adapter_lines_usa_sysfs_y_show():
    show = {
        "Controller": "AA:BB:CC:DD:EE:FF",
        "Alias": "miniserver",
        "Powered": "yes",
        "Discoverable": "no",
        "Pairable": "yes",
    }
    hcis = [
        {"hci": "hci0", "address": "AA:BB:CC:DD:EE:FF", "driver": "btusb", "bus": "usb"}
    ]
    text = "\n".join(tui.adapter_lines(show, hcis))
    assert "hci0" in text
    assert "miniserver" in text
    assert "btusb (usb)" in text
    assert "powered      yes" in text


def test_adapter_lines_fallback_sin_hci():
    lines = tui.adapter_lines({"Controller": "AA:BB:CC:DD:EE:FF"}, [])
    assert lines[0] == "Adaptador  -  AA:BB:CC:DD:EE:FF"
    assert lines[-1] == "  driver       - (-)"


def test_build_rows_fusiona_known_y_nearby():
    known_devs = [
        {"mac": "11:11:11:11:11:11", "name": "telefono", "trusted": True},
        {"mac": "22:22:22:22:22:22", "name": "", "trusted": False},
    ]
    nearby = [
        {"mac": "22:22:22:22:22:22", "name": "vecino"},
        {"mac": "33:33:33:33:33:33", "name": "nuevo"},
    ]
    rows = tui.build_rows(known_devs, nearby)
    assert [r["mac"] for r in rows] == [
        "11:11:11:11:11:11",
        "22:22:22:22:22:22",
        "33:33:33:33:33:33",
    ]
    assert rows[0]["trusted"] and rows[0]["known"] and not rows[0]["present"]
    assert rows[1]["present"] and not rows[1]["trusted"]
    assert not rows[2]["known"] and rows[2]["present"]


def test_move_selection_envuelve():
    assert tui.move_selection(0, -1, 3) == 2
    assert tui.move_selection(2, 1, 3) == 0
    assert tui.move_selection(1, 1, 3) == 2
    assert tui.move_selection(0, 1, 0) == 0


def test_progress_bar():
    assert tui.progress_bar(None, 100) == "?"
    assert tui.progress_bar(50, 100, width=10) == "#####----- 50/100 (50%)"
    assert tui.progress_bar(0, None, width=4) == "---- 0/? (0%)"


def test_parse_info_y_detail_lines():
    info = tui.parse_info("Device AA:BB (public)\n\tName: braiidev\n\tTrusted: yes\n")
    assert info["Name"] == "braiidev"
    assert info["Trusted"] == "yes"
    row = {"mac": "AA:BB", "name": "braiidev", "trusted": True, "present": True}
    text = "\n".join(tui.detail_lines(row, info))
    assert "AA:BB" in text
    assert "trusted" in text
    assert "presente:si" in text
    assert "Trusted    yes" in text
    assert tui.detail_lines(None, {}) == ["  (sin seleccion)"]


def test_render_screen_lista_y_seleccion():
    state = {
        "show": {"Powered": "yes"},
        "hcis": [],
        "rows": [
            {
                "mac": "11:11",
                "name": "a",
                "trusted": True,
                "known": True,
                "present": False,
            },
            {
                "mac": "22:22",
                "name": "b",
                "trusted": False,
                "known": False,
                "present": True,
            },
        ],
        "selection": 1,
        "selected": {"mac": "22:22", "name": "b", "trusted": False, "present": True},
        "detail": {},
        "message": "",
        "progress": "",
        "input": None,
        "help": False,
    }
    text = "\n".join(tui.render_screen(state))
    assert "Dispositivos (2)" in text
    assert any(
        line.strip().startswith(">") and "22:22" in line
        for line in tui.render_screen(state)
    )
    assert "11:11" in text
    assert "[trusted]" in text


def test_render_screen_ayuda_e_input_y_progreso():
    base = {"rows": [], "selection": 0, "selected": None, "detail": {}, "help": True}
    assert "Ayuda" in "\n".join(tui.render_screen(base))
    base["help"] = False
    base["input"] = {"prompt": "enviar a X: ", "buffer": "/tmp/a"}
    assert "/tmp/a_" in "\n".join(tui.render_screen(base))
    base["input"] = None
    base["progress"] = "## 2/4"
    assert "progreso: ## 2/4" in "\n".join(tui.render_screen(base))


class _FakeStdout:
    def isatty(self) -> bool:
        return False


def test_run_sin_tty_devuelve_error(monkeypatch, capsys):
    monkeypatch.setattr(tui.sys, "stdout", _FakeStdout())
    assert tui.run() == 1
    assert "requiere una terminal" in capsys.readouterr().err
