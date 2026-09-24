"""TUI curses base: estado del adaptador, conocidos y descubrimiento.

La logica de armado de pantalla vive en funciones puras (adapter_lines,
device_lines, screen_lines) para poder testearla sin curses. La app curses
importa curses de forma diferida y solo orquesta teclas y redibujo.
"""

from __future__ import annotations

import subprocess
import sys

from btui import diagnostic as diag
from btui import devices as devmod
from btui import known

HELP = "r refrescar  d descubrir  q salir"


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


def device_lines(devices: list[dict], known_macs: set[str] | None = None) -> list[str]:
    known_macs = known_macs or set()
    lines: list[str] = []
    for dev in devices:
        mac = dev.get("mac", "")
        name = dev.get("name", "") or "-"
        if dev.get("trusted"):
            tag, mark = "trusted", "*"
        elif mac in known_macs:
            tag, mark = "known", " "
        else:
            tag, mark = "-", " "
        lines.append(f"  {mark} {mac}  {name:<20} [{tag}]")
    return lines


def screen_lines(
    show: dict[str, str],
    hcis: list[dict[str, str]],
    known_devs: list[dict],
    nearby: list[dict] | None,
    message: str,
) -> list[str]:
    lines: list[str] = []
    lines += adapter_lines(show, hcis)
    lines.append("-" * 52)
    lines.append(f"Conocidos ({len(known_devs)})")
    lines += device_lines(known_devs) or ["  (ninguno)"]
    if nearby is not None:
        known_macs = {d.get("mac", "") for d in known_devs}
        lines.append("-" * 52)
        lines.append(f"Cercanos ({len(nearby)})")
        lines += device_lines(nearby, known_macs) or ["  (ninguno)"]
    lines.append("-" * 52)
    lines.append(message or HELP)
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


def _main(stdscr) -> int:
    import curses
    import threading

    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(200)
    state: dict = {"nearby": None, "scanning": False, "message": ""}

    def worker() -> None:
        found = devmod.scan(6)
        state["nearby"] = found
        state["message"] = f"descubrimiento: {len(found)} dispositivo(s)"
        state["scanning"] = False

    while True:
        message = "escaneando..." if state["scanning"] else state["message"]
        lines = screen_lines(
            run_show(), diag.inspect_sysfs(), known.load(), state["nearby"], message
        )
        _draw(stdscr, lines)
        key = stdscr.getch()
        if key == -1:
            continue
        if key in (ord("q"), ord("Q")):
            return 0
        if key in (ord("d"), ord("D")) and not state["scanning"]:
            state["scanning"] = True
            state["message"] = ""
            threading.Thread(target=worker, daemon=True).start()


def run() -> int:
    import curses

    if not sys.stdout.isatty():
        print("error: --tui requiere una terminal interactiva", file=sys.stderr)
        return 1
    try:
        return curses.wrapper(_main)
    except KeyboardInterrupt:
        return 130
