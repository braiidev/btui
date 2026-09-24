from btui import tui

HINT_STATE = {
    "mode": "main",
    "show": {
        "Alias": "btui",
        "Powered": "yes",
        "Discoverable": "yes",
        "Pairable": "yes",
    },
    "hcis": [{"hci": "hci0", "address": "AA:BB", "driver": "btusb"}],
    "rows": [],
}


def test_header_y_detalle_estilos():
    st = dict(HINT_STATE)
    st["focus"] = "devices"
    st["mode"] = "detail"
    st["detail_lines"] = ["  AA:BB  nombre  [trusted]  presente:si"]
    lines = tui.screen_lines(st)
    assert tui.line_style(st, 0, lines[0]) == "header"
    assert tui.line_style(st, 1, lines[1]) == "header"
    detail = [l for l in lines if "[trusted]" in l][0]
    idx = lines.index(detail)
    assert tui.line_style(st, idx, detail) == "tag-trusted"


def test_titulos_y_hint():
    st = dict(HINT_STATE)
    st["focus"] = "devices"
    lines = tui.screen_lines(st)
    title = [l for l in lines if l.strip().startswith("Dispositivos alrededor")][0]
    idx = lines.index(title)
    assert tui.line_style(st, idx, title) == "title"
    hint = [l for l in lines if l.strip() == tui.HINT][0]
    assert tui.line_style(st, lines.index(hint), hint) == "hint"


def test_seleccion_reverse_y_tags():
    st = dict(HINT_STATE)
    st["focus"] = "devices"
    st["rows"] = [
        {
            "mac": "AA:BB",
            "name": "a",
            "trusted": True,
            "known": True,
            "present": False,
        },
    ]
    lines = tui.screen_lines(st)
    selected = [l for l in lines if l.startswith(" >")][0]
    assert tui.line_style(st, lines.index(selected), selected) == "selected"
    tagged = [l for l in lines if "[trusted]" in l][0]
    assert tui.line_style(st, lines.index(tagged), tagged) == "tag-trusted"


def test_confirm_danger():
    st = dict(HINT_STATE)
    st["mode"] = "confirm"
    st["confirm"] = {"msg": "Quitar AA?"}
    lines = tui.screen_lines(st)
    assert tui.line_style(st, 0, lines[0]) == "danger"


def test_atajo_de_teclado_es_hint():
    st = dict(HINT_STATE)
    st["mode"] = "menu"
    st["menu"] = [{"id": "connect", "label": "Conectar"}]
    lines = tui.screen_lines(st)
    tip = [l for l in lines if l.strip().startswith("Enter")][0]
    assert tui.line_style(st, lines.index(tip), tip) == "hint"


def test_progreso_style():
    assert tui.line_style({}, 3, f"progreso: {tui.progress_bar(10, 20)}") == "progress"


def test_theme_atributos_sin_color():
    import curses

    assert tui._curse_attr("plain", False) == 0
    assert tui._curse_attr("selected", False) == curses.A_REVERSE
    assert tui._curse_attr("title", False) == curses.A_BOLD
    assert tui._curse_attr("hint", False) == curses.A_DIM


def test_theme_mapa_colores():
    import curses

    assert tui._THEME["tag-trusted"][0] == 32
    assert tui._THEME["danger"][0] == 31
    assert tui._THEME["header"][0] == 36
    assert tui._THEME["header"][1] == curses.A_BOLD
    assert set(tui._THEME) == set(tui.STYLES)
