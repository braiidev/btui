"""TUI curses: estado del adaptador, dispositivos, acciones y envio OPP.

La logica de armado de pantalla y de seleccion vive en funciones puras
(adapter_lines, build_rows, move_selection, progress_bar, parse_info,
detail_lines, help_lines, render_screen) para testearlas sin curses. La app
curses importa curses de forma diferida y solo orquesta teclas y redibujo.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Callable

from btui import diagnostic as diag
from btui import devices as devmod
from btui import known
from btui import obex

HELP = "↑/↓ j/k mover  p parear  t trust  x denegar  i detalle  c conectar  s enviar  r refrescar  d scan  ? ayuda  q salir"
KEY_HELP = (
    "Ayuda — teclas",
    "  ↑/↓ o j/k    mover seleccion",
    "  h/l          mover (reservado)",
    "  p            parear (marca trusted)",
    "  t            trust / aceptar",
    "  x            denegar / olvidar (x de nuevo confirma)",
    "  i            detalle del dispositivo",
    "  c            conectar (exito marca trusted)",
    "  s            enviar archivo (escribi la ruta)",
    "  r            refrescar",
    "  d            descubrir cercanos (scan 6s)",
    "  ?            esta ayuda",
    "  q            salir",
)


def run_show() -> dict[str, str]:
    proc = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True)
    return diag.parse_bluez_show(proc.stdout)


def adapter_lines(show: dict[str, str], hcis: list[dict[str, str]]) -> list[str]:
    hci = hcis[0] if hcis else {}
    address = hci.get("address") or show.get("Controller") or "-"
    driver = hci.get("driver") or "-"
    bus = hci.get("bus") or "-"
    return [
        f"Adaptador  {hci.get('hci') or '-'}  {address}",
        f"  alias        {show.get('Alias') or '-'}",
        f"  powered      {show.get('Powered') or '-'}",
        f"  discoverable {show.get('Discoverable') or '-'}",
        f"  pairable     {show.get('Pairable') or '-'}",
        f"  driver       {driver} ({bus})",
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
            }
        )
    return rows


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
        return ["  (sin seleccion)"]
    state = "trusted" if row.get("trusted") else "known"
    present = "si" if row.get("present") else "no"
    lines = [
        f"  {row.get('mac', '')}  {row.get('name', '-')}  [{state}]  presente:{present}",
    ]
    for key in ("Alias", "Paired", "Trusted", "Connected", "UUID"):
        if info.get(key):
            lines.append(f"  {key:<10} {info[key]}")
    return lines


def render_screen(state: dict) -> list[str]:
    lines: list[str] = []
    if state.get("help"):
        lines += list(KEY_HELP)
        lines.append("")
        lines.append("cualquier tecla vuelve")
        return lines
    lines += adapter_lines(state.get("show", {}), state.get("hcis", []))
    lines.append("-" * 60)
    rows: list[dict] = state.get("rows", [])
    selection: int = state.get("selection", 0)
    lines.append(f"Dispositivos ({len(rows)})")
    if not rows:
        lines.append("  (ninguno; usa d para descubrir)")
    for i, row in enumerate(rows):
        mark = ">" if i == selection else " "
        star = "*" if row.get("trusted") else " "
        tag = (
            "trusted" if row.get("trusted") else ("known" if row.get("known") else "-")
        )
        pres = "+" if row.get("present") else " "
        lines.append(
            f" {mark}{star} {pres} {row.get('mac', '')}  {row.get('name', '-'):<20} [{tag}]"
        )
    lines.append("-" * 60)
    lines.append("Detalle")
    lines += detail_lines(state.get("selected"), state.get("detail", {}))
    lines.append("-" * 60)
    if state.get("input") is not None:
        lines.append(f"{state['input']['prompt']}{state['input']['buffer']}_")
    elif state.get("progress"):
        lines.append(f"progreso: {state['progress']}")
    else:
        lines.append(state.get("message", "") or HELP)
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

    state["busy"] = True

    def worker() -> None:
        try:
            state["message"] = fn() or ""
        except Exception as exc:  # noqa: BLE001
            state["message"] = f"error: {exc}"
        state["known"] = known.load()
        state["busy"] = False

    threading.Thread(target=worker, daemon=True).start()


def _refresh_nearby(state: dict) -> None:
    import threading

    state["scanning"] = True

    def worker() -> None:
        found = devmod.scan(6)
        state["nearby"] = found
        state["message"] = f"descubrimiento: {len(found)} dispositivo(s)"
        state["scanning"] = False

    threading.Thread(target=worker, daemon=True).start()


def _handle_input(state: dict, key: int) -> None:
    import curses

    inp = state["input"]
    if key in (10, 13, curses.KEY_ENTER):
        path = inp["buffer"].strip()
        state["input"] = None
        row = state.get("selected")
        if not path or row is None:
            state["message"] = "envio cancelado"
            return
        mac = row["mac"]
        if not row.get("trusted"):
            state["message"] = f"{mac} no es trusted; no se envia"
            return
        state["progress"] = ""

        def cb(transferred, size, name):
            state["progress"] = f"{progress_bar(transferred, size)}  {name}"

        def action() -> str:
            rc = obex.send([path], mac, progress=cb, announce=False)
            state["progress"] = ""
            return "envio completo" if rc == 0 else "envio fallo"

        _run_action(state, action)
    elif key in (27,):
        state["input"] = None
        state["message"] = "cancelado"
    elif key in (curses.KEY_BACKSPACE, 127, 8):
        inp["buffer"] = inp["buffer"][:-1]
    elif 32 <= key < 127:
        inp["buffer"] += chr(key)


def _action_for(state: dict, key: int) -> None:
    row = state.get("selected")
    if row is None:
        state["message"] = "sin dispositivo seleccionado"
        return
    mac = row["mac"]
    if key == ord("p"):
        _run_action(state, lambda: (devmod.pair(mac), "pareado")[1])
    elif key == ord("t"):
        _run_action(state, lambda: (devmod.accept(mac), "trusted")[1])
    elif key == ord("x"):
        if state.get("confirm") == mac:
            state["confirm"] = None
            _run_action(state, lambda: (devmod.deny(mac), "denegado")[1])
        else:
            state["confirm"] = mac
            state["message"] = f"confirmá con x de nuevo para denegar {mac}"
    elif key == ord("c"):
        _run_action(state, lambda: _connect(mac))
    elif key == ord("i"):
        _run_action(state, lambda: _load_detail(state, mac))
    elif key == ord("s"):
        state["input"] = {"prompt": f"enviar a {mac}: ", "buffer": ""}


def _connect(mac: str) -> str:
    rc = devmod._run("bluetoothctl", "connect", mac).returncode
    if rc == 0:
        known.set_trusted(mac, True)
        return "conectado (trusted)"
    return "conexion fallida"


def _load_detail(state: dict, mac: str) -> str:
    res = devmod._run("bluetoothctl", "info", mac)
    state["detail"] = parse_info(res.stdout)
    state["detail_mac"] = mac
    return "detalle actualizado"


def _main(stdscr) -> int:
    import curses

    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(150)
    state: dict = {
        "known": known.load(),
        "nearby": None,
        "selection": 0,
        "detail": {},
        "detail_mac": None,
        "message": "",
        "progress": "",
        "help": False,
        "input": None,
        "scanning": False,
        "busy": False,
        "confirm": None,
    }
    while True:
        state["rows"] = build_rows(state["known"], state["nearby"])
        count = len(state["rows"])
        if count:
            state["selection"] = min(state["selection"], count - 1)
            state["selected"] = state["rows"][state["selection"]]
        else:
            state["selected"] = None
        if state["selected"] and state["selected"]["mac"] != state.get("detail_mac"):
            state["detail"] = {}
        _draw(stdscr, render_screen(state))
        key = stdscr.getch()
        if key == -1:
            continue
        if state.get("help"):
            state["help"] = False
            continue
        if state.get("input") is not None:
            _handle_input(state, key)
            continue
        if key in (ord("q"), ord("Q")):
            return 0
        if key in (curses.KEY_UP, ord("k")):
            state["selection"] = move_selection(state["selection"], -1, count)
            state["confirm"] = None
        elif key in (curses.KEY_DOWN, ord("j")):
            state["selection"] = move_selection(state["selection"], 1, count)
            state["confirm"] = None
        elif key in (ord("h"), ord("l")):
            pass
        elif key in (ord("?"),):
            state["help"] = True
        elif key in (ord("r"), ord("R"), curses.KEY_RESIZE):
            state["message"] = ""
        elif key in (ord("d"), ord("D")) and not state["scanning"]:
            state["message"] = ""
            _refresh_nearby(state)
        elif key in (ord("p"), ord("t"), ord("x"), ord("c"), ord("i"), ord("s")):
            _action_for(state, key)


def run() -> int:
    import curses

    if not sys.stdout.isatty():
        print("error: --tui requiere una terminal interactiva", file=sys.stderr)
        return 1
    try:
        return curses.wrapper(_main)
    except KeyboardInterrupt:
        return 130
