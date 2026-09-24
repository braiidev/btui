from btui import menu


def test_menu_lines_marca_seleccion():
    state = {"selection": 1, "message": "hola", "input": None}
    lines = menu.menu_lines(state)
    assert lines[0].startswith("btui")
    assert any(line.startswith(" > ") for line in lines)
    assert "hola" in lines


def test_menu_lines_input():
    state = {
        "selection": 0,
        "message": "",
        "input": {"prompt": "alias: ", "buffer": "pc"},
    }
    assert "alias: pc_" in "\n".join(menu.menu_lines(state))


def test_move_selection_envuelve():
    assert menu.move_selection(0, -1, len(menu.MENU)) == len(menu.MENU) - 1
    assert menu.move_selection(len(menu.MENU) - 1, 1, len(menu.MENU)) == 0


def test_capture_ok_y_error():
    assert menu._capture(lambda: 0) == (0, "ok")
    assert menu._capture(lambda: 1) == (1, "error")

    def prints():
        print("linea util")
        return 0

    assert menu._capture(prints) == (0, "linea util")


def test_dispatch_quit_y_terminal():
    state: dict = {"message": "", "input": None}
    menu._dispatch(state, "quit")
    assert state["quit"] is True
    menu._dispatch(state, "tui")
    assert state["terminal"][-1] == "--tui"
    menu._dispatch(state, "name")
    assert state["input"]["kind"] == "name"


def test_submit_input_name(monkeypatch):
    calls: list[str] = []

    class _Radio:
        @staticmethod
        def set_alias(alias: str) -> int:
            assert alias == "pc"
            return 0

    monkeypatch.setattr(menu, "_thread", lambda state, fn: calls.append(fn()[1]))
    import btui.radio as radio

    monkeypatch.setattr(radio, "set_alias", _Radio.set_alias)
    state = {"input": {"prompt": "alias: ", "buffer": "pc", "kind": "name"}}
    menu._submit_input(state)
    assert state["input"] is None
    assert calls == ["ok"]


def test_submit_input_receive_arma_terminal(tmp_path, monkeypatch):
    monkeypatch.setattr(menu.config, "config_dir", lambda: tmp_path)
    state = {"input": {"prompt": "dir: ", "buffer": "/tmp/x", "kind": "receive"}}
    menu._submit_input(state)
    assert state["terminal"][-2:] == ["--receive", "/tmp/x"]
    assert menu.config.get_receive_dir() == "/tmp/x"
