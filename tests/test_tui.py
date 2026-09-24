from btui import tui


def test_adapter_panel_incluye_radio_y_nombre():
    show = {
        "Powered": "no",
        "Alias": "miniserver",
        "Discoverable": "no",
        "Pairable": "yes",
    }
    items = tui.adapter_panel(show)
    assert items[0]["id"] == "radio"
    assert items[0]["label"] == "Encender radio"
    assert items[1]["value"] == "miniserver"
    assert (
        tui.adapter_panel({"Powered": "yes", "Discoverable": "yes"})[0]["label"]
        == "Apagar radio"
    )


def test_adapter_lines_muestra_resumen():
    show = {
        "Powered": "yes",
        "Discoverable": "no",
        "Pairable": "yes",
        "Alias": "x",
        "Controller": "AA:BB",
    }
    lines = tui.adapter_lines(
        show, [{"hci": "hci0", "address": "AA:BB", "driver": "btusb"}]
    )
    assert "radio on" in "\n".join(lines)
    assert "btusb" in "\n".join(lines)


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
    assert rows[0]["trusted"] and not rows[0]["present"]
    assert rows[1]["present"] and not rows[1]["trusted"]
    assert not rows[2]["known"] and rows[2]["present"]


def test_devices_rows_prefix_global_actions():
    state = {
        "rows": [
            {"mac": "AA", "name": "a", "trusted": True, "known": True, "present": False}
        ]
    }
    rows = tui.devices_rows(state)
    assert [r["id"] for r in rows if r["kind"] == "action"] == ["scan", "receive"]
    assert rows[-1]["kind"] == "device"


def test_device_menu_items_segun_estado():
    no_known = {"known": False, "trusted": False}
    trusted = {"known": True, "trusted": True}
    no_trusted = {"known": True, "trusted": False}
    assert tui.device_menu_items(no_known)[0]["id"] == "pair"
    assert "connect" in [i["id"] for i in tui.device_menu_items(trusted)]
    assert "send" in [i["id"] for i in tui.device_menu_items(trusted)]
    assert "connect" not in [i["id"] for i in tui.device_menu_items(no_trusted)]
    assert "send" not in [i["id"] for i in tui.device_menu_items(no_trusted)]


def test_move_selection_envuelve():
    assert tui.move_selection(0, -1, 3) == 2
    assert tui.move_selection(2, 1, 3) == 0
    assert tui.move_selection(0, 1, 0) == 0


def test_progress_bar():
    assert tui.progress_bar(None, 100) == "?"
    assert tui.progress_bar(50, 100, width=10) == "#####----- 50/100 (50%)"


def test_parse_info_y_detail_lines():
    info = tui.parse_info("Device AA:BB (public)\n\tName: braiidev\n\tTrusted: yes\n")
    assert info["Name"] == "braiidev"
    row = {"mac": "AA:BB", "name": "braiidev", "trusted": True, "present": True}
    text = "\n".join(tui.detail_lines(row, info))
    assert "AA:BB" in text and "presente:si" in text and "Trusted    yes" in text
    assert tui.detail_lines(None, {}) == ["  (sin equipo seleccionado)"]


def test_screen_lines_3_secciones_y_foco():
    state = {
        "show": {"Powered": "yes"},
        "hcis": [],
        "rows": [
            {
                "mac": "AA",
                "name": "a",
                "trusted": True,
                "known": True,
                "present": False,
            },
        ],
        "focus": "adapter",
        "adapter_sel": 0,
        "sel": 0,
        "mode": "main",
        "input": None,
        "progress": "",
        "busy": False,
        "message": "",
    }
    text = "\n".join(tui.screen_lines(state))
    assert "Mi adaptador" in text
    assert "Dispositivos alrededor (1)" in text
    assert "Descubrir cercanos" in text
    state["focus"] = "devices"
    text2 = "\n".join(tui.screen_lines(state))
    assert "> Descubrir cercanos" in text2


def test_screen_lines_menu_confirm_detalle():
    base = {
        "show": {},
        "hcis": [],
        "selected": {"mac": "AA", "name": "a"},
        "mode": "menu",
    }
    base["menu"] = [
        {"id": "connect", "label": "Conectar"},
        {"id": "cancel", "label": "Cancelar"},
    ]
    base["menu_sel"] = 0
    assert "Conectar" in "\n".join(tui.screen_lines(base))
    base["mode"] = "confirm"
    base["confirm"] = {"msg": "Quitar AA?"}
    base["confirm_sel"] = 1
    assert "Quitar AA?" in "\n".join(tui.screen_lines(base))
    base["mode"] = "detail"
    base["detail_lines"] = ["  Aliased: x"]
    base["detail_title"] = "Detalle"
    assert "Aliased: x" in "\n".join(tui.screen_lines(base))
    base["mode"] = "help"
    assert "cualquier tecla vuelve" in "\n".join(tui.screen_lines(base))


def test_screen_lines_input_y_progreso():
    state = {
        "show": {},
        "hcis": [],
        "rows": [],
        "focus": "adapter",
        "adapter_sel": 0,
        "sel": 0,
        "mode": "main",
        "busy": False,
        "progress": "",
        "message": "",
    }
    state["input"] = {"prompt": "archivo: ", "buffer": "/tmp/a"}
    assert "/tmp/a_" in "\n".join(tui.screen_lines(state))
    state["input"] = None
    state["progress"] = "## 2/4"
    assert "progreso: ## 2/4" in "\n".join(tui.screen_lines(state))


class _FakeStdout:
    def isatty(self) -> bool:
        return False


def test_run_sin_tty_devuelve_error(monkeypatch, capsys):
    monkeypatch.setattr(tui.sys, "stdout", _FakeStdout())
    assert tui.run() == 1
    assert "requiere una terminal" in capsys.readouterr().err


def _base_state() -> dict:
    return {
        "show": {
            "Powered": "yes",
            "Alias": "btui",
            "Discoverable": "yes",
            "Pairable": "yes",
        },
        "hcis": [],
        "rows": [],
        "focus": "devices",
        "adapter_sel": 0,
        "sel": 0,
        "mode": "main",
        "menu": [],
        "menu_sel": 0,
        "input": None,
        "detail_lines": [],
        "message": "",
        "busy": False,
    }


def test_receive_action_abre_input_con_modo_input():
    state = _base_state()
    tui._devices_action(state, {"kind": "action", "id": "receive"})
    assert state["mode"] == "input"
    assert state["input"]["kind"] == "receive"
    assert state["input"]["buffer"] == "/tmp/recibidos"


def test_send_menu_abre_input_con_modo_input():
    state = _base_state()
    state["selected"] = {"mac": "AA:BB", "name": "pc"}
    tui._menu_choose(state, "send")
    assert state["mode"] == "input"
    assert state["input"]["kind"] == "send"
    assert state["input"]["mac"] == "AA:BB"


def test_name_action_abre_input_con_modo_input():
    state = _base_state()
    tui._adapter_action(state, "name")
    assert state["mode"] == "input"
    assert state["input"]["kind"] == "name"


def test_handle_input_edita_y_no_dispara_acciones():
    import curses

    state = _base_state()
    state["mode"] = "input"
    state["input"] = {"prompt": "x: ", "buffer": "", "kind": "name"}
    for ch in "archivo.txt":
        tui._handle_input(state, ord(ch))
    tui._handle_input(state, curses.KEY_BACKSPACE)
    assert state["input"]["buffer"] == "archivo.tx"
    assert state["mode"] == "input"
    tui._handle_input(state, 27)
    assert state["input"] is None
    assert state["mode"] == "main"


def test_input_modo_ignora_teclas_de_navegacion():
    import curses

    state = _base_state()
    state["mode"] = "input"
    state["input"] = {"prompt": "x: ", "buffer": "/tmp", "kind": "receive"}
    tui._handle_input(state, ord("k"))
    tui._handle_input(state, ord("j"))
    tui._handle_input(state, ord("q"))
    assert state["mode"] == "input"
    assert state["input"]["buffer"] == "/tmpk jq".replace(" ", "")
