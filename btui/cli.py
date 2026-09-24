"""CLI one-shot de btui para verificaciones rapidas.

Las operaciones de ciclo de vida (install/uninstall/update/start/stop/restart)
y el resto de flags se incorporan en fases siguientes (ver TODO.md).
"""

from __future__ import annotations

import argparse
import sys

from btui import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="btui",
        description="Gestion de Bluetooth (Alpine). CLI one-shot para verificaciones rapidas.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="muestra la version y sale",
    )
    return parser


def run(argv: list[str]) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.version:
        print(f"btui {__version__}")
        return 0
    parser.print_help()
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv)