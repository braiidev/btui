"""Menu curses: front-end interactivo del CLI.

Corre las acciones ya existentes de btui (info, radio, lifecycle, envio,
receive, update) sin logica Bluetooth nueva. Las acciones que necesitan la
terminal (TUI, receive) suspenden curses y se ejecutan en primer plano; el
resto se corre en un hilo capturando salida para mostrarla como mensaje.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import threading
from typing import Callable

from btui import __version__
from btui import cli
from btui import config
from btui import diagnostic as diag

MENU: list[tuple[str, str]] = [
    ("info", "Estado / diagnostico"),
    ("tui", "TUI de dispositivos"),
    ("on", "Encender radio"),
    ("off", "Apagar radio"),
    ("name", "Renombrar adaptador"),
    ("discoverable", "Visible (toggle)"),
    ("pairable", "Pairable (toggle)"),
    ("send", "Enviar archivo"),
    ("receive", "Recibir OPP (escuchar)"),
    ("check-update", "Chequear actualizacion"),
    ("start", "Servicio: iniciar"),
    ("stop", "Servicio: detener"),
    ("restart", "Servicio: reiniciar"),
    ("update", "Actualizar btui"),
    ("install", "Instalar"),
    ("uninstall", "Desinstalar"),
    ("quit", "Salir"),
]

HELP = "↑/↓ j/k mover  Enter ejecutar  q salir"
_TERMINAL = {"tui", "receive"}


def menu_lines(state: dict) -> list[str]:
    lines = [f"btui {__version__} — menu", "-" * 40]
    selection = state.get("selection", 0)
    for i, (_item_id, label) in enumerate(MENU):
        mark = ">" if i == selection else " "
        lines.append(f" {mark} {label}")
    lines.append("-" * 40)
    if state.get("input") is not None:
        lines.append(f"{state['input']['prompt']}{state['input']['buffer']}_")
    else:
        lines.append(state.get("message", "") or HELP)
    return lines


def move_selection(index: int, delta: int, count: int) -> int:
    if count <= 0:
        return 0
    return (index + delta) % count


def _show() -> dict[str, str]:
    proc = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True)
    return diag.parse_bluez_show(proc.stdout)


def _capture(fn: Callable[[], int]) -> tuple[int, str]:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = fn()
    except Exception as exc:  # noqa: BLE001
        return 1, f"error: {exc}"
    out = [line for line in buf.getvalue().strip().splitlines() if line.strip()]
    return rc or 0, out[-1] if out else ("ok" if rc == 0 else "error")


def _privileged(flag: str) -> tuple[int, str]:
    if cli._is_root():
        cmd = ["sh", str(cli.REPO_ROOT / "install.sh"), flag]
    else:
        cmd = ["sudo", cli.BIN_PATH, flag]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    return proc.returncode, (
        out[-1] if out else ("ok" if proc.returncode == 0 else "error")
    )


def _thread(state: dict, fn: Callable[[], tuple[int, str]]) -> None:
    state["busy"] = True

    def worker() -> None:
        _rc, message = fn()
        state["message"] = message
        state["busy"] = False

    threading.Thread(target=worker, daemon=True).start()


def _dispatch(state: dict, item_id: str) -> None:
    if item_id == "quit":
        state["quit"] = True
    elif item_id == "tui":
        state["terminal"] = [sys.executable, "-m", "btui", "--tui"]
    elif item_id == "receive":
        state["input"] = {
            "prompt": "dir destino: ",
            "buffer": config.get_receive_dir(),
            "kind": "receive",
        }
    elif item_id == "name":
        state["input"] = {"prompt": "alias: ", "buffer": "", "kind": "name"}
    elif item_id == "send":
        state["input"] = {"prompt": "archivo: ", "buffer": "", "kind": "send"}
    elif item_id == "info":
        from btui import info

        _thread(state, lambda: _capture(info.run))
    elif item_id == "check-update":
        from btui import update

        _thread(state, lambda: _capture(update.run))
    elif item_id in ("on", "off"):
        from btui import radio

        _thread(state, lambda: _capture(lambda: radio.set_powered(item_id == "on")))
    elif item_id == "discoverable":
        from btui import radio

        current = _show().get("Discoverable") == "yes"
        _thread(state, lambda: _capture(lambda: radio.set_discoverable(not current)))
    elif item_id == "pairable":
        from btui import radio

        current = _show().get("Pairable") == "yes"
        _thread(state, lambda: _capture(lambda: radio.set_pairable(not current)))
    elif item_id in ("start", "stop", "restart", "update", "install", "uninstall"):
        flag = f"--{item_id}"
        _thread(state, lambda: _privileged(flag))


def _submit_input(state: dict) -> None:
    inp = state["input"]
    state["input"] = None
    text = inp["buffer"].strip()
    kind = inp["kind"]
    if kind == "name":
        from btui import radio

        _thread(state, lambda: _capture(lambda: radio.set_alias(text)))
    elif kind == "send":
        from btui import known, obex

        target = known.first_trusted()
        if target is None:
            state["message"] = "sin dispositivo trusted para enviar"
            return
        _thread(
            state,
            lambda: (
                0,
                (
                    "envio completo"
                    if obex.send([text], target, announce=False) == 0
                    else "envio fallo"
                ),
            ),
        )
    elif kind == "receive":
        config.set_receive_dir(text)
        state["terminal"] = [
            sys.executable,
            "-m",
            "btui",
            "--receive",
            text or config.get_receive_dir(),
        ]


def _handle_input(state: dict, key: int) -> None:
    import curses

    inp = state["input"]
    if key in (10, 13, curses.KEY_ENTER):
        _submit_input(state)
    elif key == 27:
        state["input"] = None
        state["message"] = "cancelado"
    elif key in (curses.KEY_BACKSPACE, 127, 8):
        inp["buffer"] = inp["buffer"][:-1]
    elif 32 <= key < 127:
        inp["buffer"] += chr(key)


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

    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(150)
    state: dict = {
        "selection": 0,
        "message": "",
        "input": None,
        "busy": False,
        "quit": False,
        "terminal": None,
    }
    while True:
        _draw(stdscr, menu_lines(state))
        if state["terminal"] is not None:
            cmd = state["terminal"]
            state["terminal"] = None
            curses.endwin()
            rc = subprocess.call(cmd)
            stdscr.clear()
            stdscr.refresh()
            state["message"] = "listo" if rc == 0 else f"rc={rc}"
            continue
        key = stdscr.getch()
        if key == -1:
            continue
        if state.get("input") is not None:
            _handle_input(state, key)
            continue
        if key in (ord("q"), ord("Q")):
            return 0
        if key in (curses.KEY_UP, ord("k")):
            state["selection"] = move_selection(state["selection"], -1, len(MENU))
        elif key in (curses.KEY_DOWN, ord("j")):
            state["selection"] = move_selection(state["selection"], 1, len(MENU))
        elif key in (10, 13, curses.KEY_ENTER):
            state["message"] = ""
            _dispatch(state, MENU[state["selection"]][0])
            if state.get("quit"):
                return 0


def run() -> int:
    import curses

    if not sys.stdout.isatty():
        print("error: --menu requiere una terminal interactiva", file=sys.stderr)
        return 1
    try:
        return curses.wrapper(_main)
    except KeyboardInterrupt:
        return 130
