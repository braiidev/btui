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
import time
from pathlib import Path

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
    parser.add_argument("--version", action="store_true", help="muestra la version y sale")
    parser.add_argument("--install", action="store_true", help="instala codigo + venv + wrapper + servicio")
    parser.add_argument("--update", action="store_true", help="actualiza codigo y reinicia el servicio")
    parser.add_argument("--uninstall", action="store_true", help="quita servicio, sudoers y binario")
    parser.add_argument("--start", action="store_true", help="inicia el servicio OpenRC btui")
    parser.add_argument("--stop", action="store_true", help="detiene el servicio OpenRC btui")
    parser.add_argument("--restart", action="store_true", help="reinicia el servicio OpenRC btui")
    parser.add_argument("command", nargs="?", default=None, help="'daemon' para el daemon en background")
    return parser


def _is_root() -> bool:
    return os.geteuid() == 0


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def _direct(argv: list[str]) -> int:
    action = argv[0]
    if action.startswith("--"):
        action = action[2:]
    if action in _SVC_ACTIONS:
        return _run(["rc-service", "btui", action])
    return _run(["sh", str(REPO_ROOT / "install.sh"), f"--{action}"])


def _privileged(argv: list[str]) -> int:
    if _is_root():
        return _direct(argv)
    return _run(["sudo", BIN_PATH, *argv])


def run_daemon(sleep: "function" = time.sleep) -> int:
    stop = False

    def on_signal(_signum, _frame) -> None:
        nonlocal stop
        stop = True

    import signal

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    print("btui daemon arrancando (placeholder v0.2)", flush=True)
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
    if ns.command == "daemon":
        return run_daemon()

    for action in _SVC_ACTIONS:
        if getattr(ns, action):
            return _privileged([f"--{action}"])
    for action in _SCRIPT_ACTIONS:
        if getattr(ns, action):
            return _privileged([f"--{action}"])

    parser.print_help()
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv)