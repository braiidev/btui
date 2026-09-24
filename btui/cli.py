"""CLI one-shot de btui para verificaciones rapidas.

Flags de ciclo de vida (--install/--update/--uninstall/--start/--stop/--restart):
las operaciones privilegiadas se re-ejecutan via `sudo btui <flag>` (regla
NOPASSWD a /usr/local/bin/btui) y al correr como root delegan en install.sh o
rc-service directamente.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from btui import __version__

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_PATH = "/usr/local/bin/btui"

_SVC_ACTIONS = ("start", "stop", "restart")
_SCRIPT_ACTIONS = ("install", "update", "uninstall")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="btui",
        description="Gestion de Bluetooth (Alpine). CLI one-shot para verificaciones rapidas.",
    )
    parser.add_argument(
        "--version", action="store_true", help="muestra la version y sale"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="instala codigo + venv + wrapper + servicio",
    )
    parser.add_argument(
        "--update", action="store_true", help="actualiza codigo y reinicia el servicio"
    )
    parser.add_argument(
        "--uninstall", action="store_true", help="quita servicio, sudoers y binario"
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="consulta el remoto y avisa si hay version nueva",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="diagnostico de driver/hardware del adaptador",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="interfaz curses: estado del adaptador, conocidos y descubrimiento",
    )
    parser.add_argument(
        "--on", action="store_true", help="enciende el radio del adaptador"
    )
    parser.add_argument(
        "--off", action="store_true", help="apaga el radio del adaptador"
    )
    parser.add_argument(
        "--name",
        metavar="ALIAS",
        default=None,
        help="renombra el adaptador (system-alias)",
    )
    parser.add_argument(
        "--discoverable",
        choices=("on", "off"),
        default=None,
        help="hace visible el adaptador a otros dispositivos",
    )
    parser.add_argument(
        "--pairable",
        choices=("on", "off"),
        default=None,
        help="acepta/rechaza pareados entrantes",
    )
    parser.add_argument(
        "--send",
        nargs="+",
        metavar="ARCHIVO",
        default=None,
        help="envia archivos por OPP (Object Push) al destino",
    )
    parser.add_argument(
        "--receive",
        metavar="DIR",
        default=None,
        help="escucha pushes OPP y los guarda en DIR (solo equipos trusted)",
    )
    parser.add_argument(
        "--to",
        metavar="MAC",
        default=None,
        help="destino del envio (por defecto: primer dispositivo conocido trusted)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        metavar="SEG",
        default=None,
        help="timeout de visibilidad (solo con --discoverable on)",
    )
    parser.add_argument(
        "--start", action="store_true", help="inicia el servicio OpenRC btui"
    )
    parser.add_argument(
        "--stop", action="store_true", help="detiene el servicio OpenRC btui"
    )
    parser.add_argument(
        "--restart", action="store_true", help="reinicia el servicio OpenRC btui"
    )
    parser.add_argument(
        "--devices",
        nargs="+",
        metavar="ARG",
        default=None,
        help="list | search | pair <mac> | accept <mac> | deny <mac>",
    )
    parser.add_argument(
        "command", nargs="?", default=None, help="'daemon' para el daemon en background"
    )
    return parser


def _is_root() -> bool:
    return os.geteuid() == 0


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def _direct(argv: list[str]) -> int:
    action = argv[0]
    if action.startswith("--"):
        action = action[2:]
    if action == "devices":
        from btui import devices as devmod

        rest = argv[1:]
        act = rest[0] if rest else "list"
        mac = rest[1] if len(rest) > 1 else None
        return devmod.run_cli(act, mac)
    if action in ("on", "off"):
        from btui import radio

        return radio.set_powered(action == "on")
    if action == "name":
        from btui import radio

        return radio.set_alias(argv[1])
    if action == "discoverable":
        from btui import radio

        timeout = None
        if "--timeout" in argv:
            timeout = int(argv[argv.index("--timeout") + 1])
        return radio.set_discoverable(argv[1] == "on", timeout)
    if action == "pairable":
        from btui import radio

        return radio.set_pairable(argv[1] == "on")
    if action in _SVC_ACTIONS:
        return _run(["rc-service", "btui", action])
    return _run(["sh", str(REPO_ROOT / "install.sh"), f"--{action}"])


def _privileged(argv: list[str]) -> int:
    if _is_root():
        return _direct(argv)
    return _run(["sudo", BIN_PATH, *argv])


def run_daemon(
    sleep: "Callable[[int], object]" = time.sleep, start_agent: bool = True
) -> int:
    stop = False

    def on_signal(_signum, _frame) -> None:
        nonlocal stop
        stop = True

    import signal

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    print("btui daemon arrancando (v0.5.2: agent + bucle)", flush=True)

    if start_agent:
        from btui import agent as agent_mod

        runner = threading.Thread(target=agent_mod.run_agent_thread, daemon=True)
        runner.start()
        print(
            f"agente de pareado registrado ({agent_mod.AGENT_CAPABILITY})", flush=True
        )

    while not stop:
        sleep(1)
    print("btui daemon detenido", flush=True)
    return 0


def run(argv: list[str]) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)

    if ns.version:
        print(f"btui {__version__}")
        return 0
    if ns.check_update:
        from btui import update

        return update.run()
    if ns.info:
        from btui import info

        return info.run()
    if ns.tui:
        from btui import tui

        return tui.run()
    if ns.command == "daemon":
        return run_daemon()
    if ns.devices:
        from btui import devices as devmod

        if ns.devices[0] == "list":
            return devmod.run_cli("list", None)
        return _privileged(["--devices", *ns.devices])

    if ns.name is not None:
        return _privileged(["--name", ns.name])
    if ns.discoverable is not None:
        argv = ["--discoverable", ns.discoverable]
        if ns.timeout is not None:
            argv += ["--timeout", str(ns.timeout)]
        return _privileged(argv)
    if ns.pairable is not None:
        return _privileged(["--pairable", ns.pairable])

    if ns.send:
        from btui import known, obex

        target = ns.to
        if target is None:
            target = known.first_trusted()
        if target is None:
            print("error: sin destino; usa --to <mac>", file=sys.stderr)
            return 1
        return obex.send(ns.send, target)

    if ns.receive:
        from btui import receive

        return receive.receive(ns.receive)

    for action in _SVC_ACTIONS:
        if getattr(ns, action):
            return _privileged([f"--{action}"])
    for action in ("on", "off"):
        if getattr(ns, action):
            return _privileged([f"--{action}"])
    for action in _SCRIPT_ACTIONS:
        if getattr(ns, action):
            return _privileged([f"--{action}"])

    parser.print_help()
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv)
