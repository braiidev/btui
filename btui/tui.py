"""TUI curses: 3 secciones (cabecera / Mi adaptador / Dispositivos alrededor).

Diseño centrado en menús contextuales en vez de atajos: Tab cambia de panel,
flechas/j/k mueven, Enter ejecuta, Esc cierra. Toda la lógica compartida vive
en funciones puras (adapter_panel, devices_rows, device_menu_items,
move_selection, progress_bar, parse_info, detail_lines, screen_lines) para
testearla sin curses. La app curses se importa de forma diferida.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Callable, cast

from btui import __version__
from btui import diagnostic as diag
from btui import devices as devmod
from btui import known
from btui import obex
from btui import radio

HINT = "Tab cambiar panel · Enter accion · Esc cerrar · ? ayuda · q salir"
KEY_HELP = (
    "Ayuda",
    "  Tab            cambiar panel (Mi adaptador / Dispositivos)",
    "  ↑/↓ o j/k      mover dentro del panel",
    "  Enter          abrir menu contextual / ejecutar",
    "  Esc            cerrar menu o modal",
    "  r              refrescar estado",
    "  q              salir",
    "",
    "  En 'Dispositivos' el Enter sobre un equipo abre",
    "  sus acciones: parear, confiar, conectar, enviar,",
    "  quitar confianza y ver detalle.",
    "",
    "  Si la radio esta apagada se ofrece encenderla.",
    "",
    "cualquier tecla vuelve",
)

ADAPTER_DETAIL_KEYS = ("Controller", "Alias", "Powered", "Discoverable", "Pairable")


def run_show() -> dict[str, str]:
    proc = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True)
    return diag.parse_bluez_show(proc.stdout)


def adapter_panel(show: dict[str, str]) -> list[dict]:
    """Items configurables de la seccion 'Mi adaptador'."""
    powered_off = show.get("Powered") != "yes"
    return [
        {
            "id": "radio",
            "label": "Encender radio" if powered_off else "Apagar radio",
            "value": "",
        },
        {
            "id": "name",
            "label": "Renombrar adaptador",
            "value": show.get("Alias") or "-",
        },
        {
            "id": "discoverable",
            "label": "Visible",
            "value": show.get("Discoverable") or "-",
        },
        {
            "id": "pairable",
            "label": "Acepta pareos",
            "value": show.get("Pairable") or "-",
        },
        {"id": "info", "label": "Ver detalle del adaptador", "value": ""},
    ]


def build_rows(known_devs: list[dict], nearby: list[dict] | None) -> list[dict]:
    """Fusiona conocidos + cercanos; known/trusted salen del JSON de conocidos."""
    rows: list[dict] = []
    seen: set[str] = set()
    for dev in known_devs:
        mac = dev.get("mac", "")
        seen.add(mac)
        rows.append(
            {
                "mac": mac,
                "name": dev.get("name", "") or "-",
                "trusted": bool(dev.get("trusted")),
                "known": True,
                "present": False,
                "connected": False,
            }
        )
    for dev in nearby or []:
        mac = dev.get("mac", "")
        if mac in seen:
            for row in rows:
                if row["mac"] == mac:
                    row["present"] = True
            continue
        rows.append(
            {
                "mac": mac,
                "name": dev.get("name", "") or "-",
                "trusted": False,
                "known": False,
                "present": True,
                "connected": False,
            }
        )
    return rows


def devices_rows(state: dict) -> list[dict]:
    """Filas del panel 'Dispositivos': 2 acciones globales + equipos."""
    rows: list[dict] = [
        {"kind": "action", "id": "scan", "label": "Descubrir cercanos"},
        {"kind": "action", "id": "receive", "label": "Recibir OPP (abre receptor)"},
    ]
    for row in state.get("rows", []):
        rows.append({"kind": "device", **row})
    return rows


def device_menu_items(row: dict) -> list[dict]:
    """Menu contextual de un equipo, segun su estado."""
    if not row.get("known"):
        return [
            {"id": "pair", "label": "Parear y confiar"},
            {"id": "accept", "label": "Confiar"},
            {"id": "info", "label": "Detalle"},
            {"id": "cancel", "label": "Cancelar"},
        ]
    if row.get("trusted"):
        return [
            {"id": "connect", "label": "Conectar"},
            {"id": "disconnect", "label": "Desconectar"},
            {"id": "send", "label": "Enviar archivo"},
            {"id": "info", "label": "Detalle"},
            {"id": "deny", "label": "Quitar confianza"},
            {"id": "cancel", "label": "Cancelar"},
        ]
    return [
        {"id": "pair", "label": "Parear"},
        {"id": "accept", "label": "Confiar"},
        {"id": "info", "label": "Detalle"},
        {"id": "deny", "label": "Quitar de conocidos"},
        {"id": "cancel", "label": "Cancelar"},
    ]


def move_selection(index: int, delta: int, count: int) -> int:
    if count <= 0:
        return 0
    return (index + delta) % count


def progress_bar(transferred: int | None, size: int | None, width: int = 20) -> str:
    if transferred is None:
        return "?"
    pct = transferred * 100 // size if size else 0
    filled = pct * width // 100
    bar = "#" * filled + "-" * (width - filled)
    return f"{bar} {transferred}/{size or '?'} ({pct}%)"


def parse_info(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        head, sep, rest = line.partition(": ")
        if sep and head:
            fields[head] = rest.strip()
    return fields


def detail_lines(row: dict | None, info: dict[str, str]) -> list[str]:
    if row is None:
        return ["  (sin equipo seleccionado)"]
    state = "trusted" if row.get("trusted") else "known"
    present = "si" if row.get("present") else "no"
    lines = [
        f"  {row.get('mac', '')}  {row.get('name', '-')}  [{state}]  presente:{present}",
    ]
    for key in ("Alias", "Paired", "Trusted", "Connected", "UUID"):
        if info.get(key):
            lines.append(f"  {key:<10} {info[key]}")
    return lines


def adapter_lines(show: dict[str, str], hcis: list[dict[str, str]]) -> list[str]:
    hci = hcis[0] if hcis else {}
    address = hci.get("address") or show.get("Controller") or "-"
    driver = hci.get("driver") or "-"
    powered = "on" if show.get("Powered") == "yes" else "off"
    return [
        f"btui {__version__}  {hci.get('hci') or '-'}  {address}",
        (
            f"  alias {show.get('Alias') or '-'} · radio {powered} · "
            f"visible {show.get('Discoverable') or '-'} · "
            f"pareos {show.get('Pairable') or '-'} · driver {driver}"
        ),
    ]


def header_lines(state: dict) -> list[str]:
    return adapter_lines(state.get("show", {}), state.get("hcis", []))


def _panel_adapter(state: dict) -> list[str]:
    items = adapter_panel(state.get("show", {}))
    sel = state.get("adapter_sel", 0)
    focused = state.get("focus") == "adapter"
    lines = ["Mi adaptador (configuracion y detalle)"]
    for i, item in enumerate(items):
        mark = ">" if focused and i == sel else " "
        value = f"  [{item['value']}]" if item["value"] else ""
        lines.append(f" {mark} {item['label']}{value}")
    return lines


def _panel_devices(state: dict) -> list[str]:
    rows = devices_rows(state)
    sel = state.get("sel", 0)
    focused = state.get("focus") == "devices"
    known_count = len(state.get("rows", []))
    lines = [f"Dispositivos alrededor ({known_count})"]
    for i, row in enumerate(rows):
        mark = ">" if focused and i == sel else " "
        if row["kind"] == "action":
            lines.append(f" {mark} {row['label']}")
            continue
        star = "*" if row.get("trusted") else " "
        tag = (
            "trusted" if row.get("trusted") else ("known" if row.get("known") else "-")
        )
        pres = "+" if row.get("present") else " "
        lines.append(
            f" {mark}{star} {pres} {row.get('mac', '')}  "
            f"{row.get('name', '-'):<18} [{tag}]"
        )
    return lines


def _modal_menu(state: dict) -> list[str]:
    selected = state.get("selected") or {}
    title = f"Acciones — {selected.get('name') or selected.get('mac') or '-'}"
    lines = [title, "-" * 44]
    sel = state.get("menu_sel", 0)
    for i, item in enumerate(state.get("menu", [])):
        mark = ">" if i == sel else " "
        lines.append(f" {mark} {item['label']}")
    lines += ["", "Enter ejecutar · Esc cancelar"]
    return lines


def _modal_confirm(state: dict) -> list[str]:
    lines = [state.get("confirm", {}).get("msg", "?"), ""]
    sel = state.get("confirm_sel", 0)
    for i, opt in enumerate(("Si", "No")):
        mark = ">" if i == sel else " "
        lines.append(f" {mark} {opt}")
    lines += ["", "Enter acepta · Esc cancela"]
    return lines


def _modal_detail(state: dict) -> list[str]:
    title = state.get("detail_title", "Detalle")
    lines = [title, "-" * 44]
    lines += state.get("detail_lines") or ["  (sin datos)"]
    lines += ["", "Esc/q volver · r refrescar"]
    return lines


def screen_lines(state: dict) -> list[str]:
    mode = state.get("mode", "main")
    if mode == "menu":
        return header_lines(state) + ["-" * 60] + _modal_menu(state)
    if mode == "confirm":
        return header_lines(state) + ["-" * 60] + _modal_confirm(state)
    if mode == "detail":
        return header_lines(state) + ["-" * 60] + _modal_detail(state)
    if mode == "help":
        return header_lines(state) + ["-" * 60] + list(KEY_HELP)
    lines = header_lines(state)
    lines.append("-" * 60)
    lines += _panel_adapter(state)
    lines.append("-" * 60)
    lines += _panel_devices(state)
    lines.append("-" * 60)
    inp = state.get("input")
    if inp is not None:
        lines.append(f"{inp['prompt']}{inp['buffer']}_")
    elif state.get("progress"):
        lines.append(f"progreso: {state['progress']}")
    elif state.get("busy"):
        lines.append("trabajando...")
    else:
        lines.append(state.get("message", "") or HINT)
    return lines


def _draw(stdscr, lines: list[str]) -> None:
    import curses

    stdscr.erase()
    height, width = stdscr.getmaxyx()
    for i, line in enumerate(lines[: height - 1]):
        try:
            stdscr.addnstr(i, 0, line, width - 1)
        except curses.error:
            pass
    stdscr.refresh()


def _run_action(state: dict, fn: Callable[[], str]) -> None:
    import threading

    def worker() -> None:
        try:
            state["message"] = fn() or ""
        except Exception as exc:  # noqa: BLE001
            state["message"] = f"error: {exc}"
            state["progress"] = ""
        state["known"] = known.load()
        state["busy"] = False

    state["busy"] = True
    state["message"] = ""
    state["progress"] = ""
    state["detail_lines"] = []
    threading.Thread(target=worker, daemon=True).start()


def _refresh(state: dict) -> None:
    state["show"] = run_show()
    state["hcis"] = diag.inspect_sysfs()
    state["known"] = known.load()
    state["message"] = ""


def _refresh_nearby(state: dict) -> None:

    def worker() -> None:
        found = devmod.scan(6)
        state["nearby"] = found
        state["scanning"] = False
        state["message"] = f"descubrimiento: {len(found)} dispositivo(s)"

    state["scanning"] = True
    state["message"] = "descubriendo (6s)..."
    import threading

    threading.Thread(target=worker, daemon=True).start()


def _power_then(state: dict, then_fn: Callable[[], None]) -> None:
    import threading

    def worker() -> None:
        radio.set_powered(True)
        state["show"] = run_show()
        then_fn()
        state["busy"] = False

    state["busy"] = True
    state["message"] = "encendiendo radio..."
    threading.Thread(target=worker, daemon=True).start()


def _maybe_power(state: dict, then_fn: Callable[[], None]) -> None:
    if state.get("show", {}).get("Powered") == "yes":
        then_fn()
    else:
        state["confirm"] = {
            "msg": "La radio esta apagada. Encenderla y continuar?",
            "then": then_fn,
        }
        state["confirm_sel"] = 0
        state["mode"] = "confirm"


def _connect(mac: str) -> str:
    res = devmod._run("timeout", "30", "bluetoothctl", "connect", mac)
    if "Connected: yes" in res.stdout:
        known.set_trusted(mac, True)
        return "conectado"
    detalle = res.stderr.strip().splitlines()
    motivo = detalle[-1] if detalle else "sin detalle util"
    return f"no conecto: {motivo}"


def _disconnect(mac: str) -> str:
    res = devmod._run("timeout", "15", "bluetoothctl", "disconnect", mac)
    if res.returncode == 0 or "Successful disconnected" in res.stdout:
        return "desconectado"
    return "no desconecto"


def _load_detail(state: dict, row: dict) -> None:
    res = devmod._run("bluetoothctl", "info", row["mac"])
    info = parse_info(res.stdout)
    state["detail_lines"] = detail_lines(row, info)
    state["detail_title"] = f"Detalle — {row.get('name') or row['mac']}"


def _adapter_action(state: dict, item_id: str) -> None:
    show = state.get("show", {})
    if item_id == "radio":
        on = show.get("Powered") != "yes"

        def act() -> str:
            radio.set_powered(on)
            state["show"] = run_show()
            return "radio encendida" if on else "radio apagada"

        _run_action(state, act)
    elif item_id == "name":
        state["input"] = {"prompt": "nuevo alias: ", "buffer": "", "kind": "name"}
    elif item_id == "discoverable":
        on = show.get("Discoverable") != "yes"

        def act() -> str:
            radio.set_discoverable(on)
            state["show"] = run_show()
            return "visible on" if on else "visible off"

        _run_action(state, act)
    elif item_id == "pairable":
        on = show.get("Pairable") != "yes"

        def act() -> str:
            radio.set_pairable(on)
            state["show"] = run_show()
            return "pareos on" if on else "pareos off"

        _run_action(state, act)
    elif item_id == "info":
        state["detail_lines"] = [
            f"  {key:<12} {show.get(key, '-')}" for key in ADAPTER_DETAIL_KEYS
        ]
        state["detail_title"] = "Mi adaptador"
        state["mode"] = "detail"


def _devices_action(state: dict, row: dict) -> None:
    if row["kind"] == "action":
        if row["id"] == "scan":
            _maybe_power(state, lambda: _refresh_nearby(state))
        elif row["id"] == "receive":
            _maybe_power(
                state,
                lambda: state.__setitem__(
                    "input",
                    {
                        "prompt": "dir destino (Enter acepta): ",
                        "buffer": "/tmp/recibidos",
                        "kind": "receive",
                    },
                ),
            )
        return
    state["selected"] = row
    state["menu"] = device_menu_items(row)
    state["menu_sel"] = 0
    state["mode"] = "menu"


def _menu_choose(state: dict, item_id: str) -> None:
    if item_id == "cancel":
        state["mode"] = "main"
        return
    row = state.get("selected") or {}
    mac = row.get("mac", "")

    if item_id in ("pair", "connect"):
        state["mode"] = "main"

        def after() -> None:
            if item_id == "pair":
                _run_action(state, lambda: (devmod.pair(mac), "pareado")[1])
            else:
                _run_action(state, lambda: _connect(mac))

        _maybe_power(state, after)
    elif item_id == "accept":
        state["mode"] = "main"
        _run_action(state, lambda: (devmod.accept(mac), "usted ahora lo conoce")[1])
    elif item_id == "disconnect":
        state["mode"] = "main"
        _run_action(state, lambda: _disconnect(mac))
    elif item_id == "send":
        state["mode"] = "main"
        state["input"] = {
            "prompt": f"archivo a enviar a {row.get('name') or mac}: ",
            "buffer": "",
            "kind": "send",
            "mac": mac,
        }
    elif item_id == "info":
        _load_detail(state, row)
        state["mode"] = "detail"
    elif item_id == "deny":
        state["confirm"] = {
            "msg": f"Quitar {row.get('name') or mac}?",
            "then": lambda: _run_action(
                state, lambda: (devmod.deny(mac), "quitado")[1]
            ),
        }
        state["confirm_sel"] = 0
        state["mode"] = "confirm"


def _submit(state: dict) -> None:
    inp = state["input"]
    state["input"] = None
    state["mode"] = "main"
    text = inp["buffer"].strip()
    kind = inp["kind"]
    if kind == "name":

        def act() -> str:
            radio.set_alias(text)
            state["show"] = run_show()
            return "alias actualizado"

        _run_action(state, act)
    elif kind == "send":
        mac = inp["mac"]
        state["progress"] = ""

        def cb(transferred, size, name):
            state["progress"] = f"{progress_bar(transferred, size)}  {name}"

        def act() -> str:
            rc = obex.send([text], mac, progress=cb, announce=False)
            state["progress"] = ""
            return "envio completo" if rc == 0 else "envio fallo"

        _run_action(state, act)
    elif kind == "receive":
        state["terminal"] = [
            sys.executable,
            "-m",
            "btui",
            "--receive",
            text or "/tmp/recibidos",
        ]


def _handle_input(state: dict, key: int) -> None:
    import curses

    inp = state["input"]
    if key in (10, 13, curses.KEY_ENTER):
        _submit(state)
    elif key == 27:
        state["input"] = None
        state["mode"] = "main"
        state["message"] = "cancelado"
    elif key in (curses.KEY_BACKSPACE, 127, 8):
        inp["buffer"] = inp["buffer"][:-1]
    elif 32 <= key < 127:
        inp["buffer"] += chr(key)


def _move(state: dict, delta: int) -> None:
    if state.get("focus") == "adapter":
        items = adapter_panel(state.get("show", {}))
        state["adapter_sel"] = move_selection(
            state.get("adapter_sel", 0), delta, len(items)
        )
    else:
        rows = devices_rows(state)
        state["sel"] = move_selection(state.get("sel", 0), delta, len(rows))


def _toggle_focus(state: dict) -> None:
    state["focus"] = "devices" if state.get("focus") == "adapter" else "adapter"


def _main(stdscr) -> int:
    import curses

    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(150)
    state: dict = {
        "show": run_show(),
        "hcis": diag.inspect_sysfs(),
        "known": known.load(),
        "nearby": None,
        "rows": [],
        "selected": None,
        "focus": "adapter",
        "adapter_sel": 0,
        "sel": 0,
        "mode": "main",
        "menu": [],
        "menu_sel": 0,
        "confirm": None,
        "confirm_sel": 0,
        "input": None,
        "detail_lines": [],
        "detail_title": "Detalle",
        "message": "",
        "progress": "",
        "busy": False,
        "scanning": False,
        "terminal": None,
    }
    while True:
        state["rows"] = build_rows(state["known"], state["nearby"])
        drows = devices_rows(state)
        state["sel"] = min(state["sel"], max(0, len(drows) - 1))
        adapter_items = adapter_panel(state.get("show", {}))
        state["adapter_sel"] = min(state["adapter_sel"], max(0, len(adapter_items) - 1))
        _draw(stdscr, screen_lines(state))
        if state.get("terminal") is not None:
            terminal_cmd = cast(list[str], state["terminal"])
            state["terminal"] = None
            curses.endwin()
            rc = subprocess.call(terminal_cmd)
            stdscr.clear()
            stdscr.refresh()
            _refresh(state)
            state["message"] = "listo" if rc == 0 else f"rc={rc}"
            continue
        key = stdscr.getch()
        if key == -1:
            continue
        mode = state["mode"]
        if mode == "help":
            state["mode"] = "main"
        elif mode == "input":
            _handle_input(state, key)
        elif mode == "menu":
            if key == 27:
                state["mode"] = "main"
            elif key in (curses.KEY_UP, ord("k")):
                state["menu_sel"] = move_selection(
                    state["menu_sel"], -1, len(state["menu"])
                )
            elif key in (curses.KEY_DOWN, ord("j")):
                state["menu_sel"] = move_selection(
                    state["menu_sel"], 1, len(state["menu"])
                )
            elif key in (10, 13, curses.KEY_ENTER):
                _menu_choose(state, state["menu"][state["menu_sel"]]["id"])
        elif mode == "confirm":
            if key == 27:
                state["mode"] = "main"
            elif key in (curses.KEY_UP, ord("k"), curses.KEY_DOWN, ord("j")):
                state["confirm_sel"] = 1 - state["confirm_sel"]
            elif key in (10, 13, curses.KEY_ENTER):
                conf = state["confirm"]
                state["mode"] = "main"
                if state["confirm_sel"] == 0 and conf:
                    conf["then"]()
        elif mode == "detail":
            if key in (27, ord("q")):
                state["mode"] = "main"
            elif key in (ord("r"), ord("R")):
                state["mode"] = "main"
                if state["selected"]:
                    _load_detail(state, state["selected"])
                    state["mode"] = "detail"
        else:
            if key in (ord("q"), ord("Q")):
                return 0
            if key in (ord("?"),):
                state["mode"] = "help"
            elif key in (9, curses.KEY_BTAB):
                _toggle_focus(state)
            elif key in (curses.KEY_UP, ord("k")):
                _move(state, -1)
            elif key in (curses.KEY_DOWN, ord("j")):
                _move(state, 1)
            elif key in (10, 13, curses.KEY_ENTER):
                if state["focus"] == "adapter":
                    _adapter_action(state, adapter_items[state["adapter_sel"]]["id"])
                else:
                    _devices_action(state, drows[state["sel"]])
            elif key in (ord("r"), ord("R"), curses.KEY_RESIZE):
                _refresh(state)


def run() -> int:
    import curses

    if not sys.stdout.isatty():
        print("error: --tui requiere una terminal interactiva", file=sys.stderr)
        return 1
    try:
        return curses.wrapper(_main)
    except KeyboardInterrupt:
        return 130
