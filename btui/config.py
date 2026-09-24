"""Configuracion persistente de btui en ~/.config/btui/.

Hoy guarda solo el directorio de recepcion OPP: el que elegiste la ultima vez
se conserva y se usa como prefijo en la TUI y el menu.
"""

from __future__ import annotations

from pathlib import Path

from btui.known import config_dir

DEFAULT_RECEIVE_DIR = "/tmp/recibidos"


def receive_file(cfg: Path | None = None) -> Path:
    return (cfg or config_dir()) / "receive.txt"


def get_receive_dir(cfg: Path | None = None) -> str:
    path = receive_file(cfg)
    try:
        text = path.read_text().strip()
    except OSError:
        return DEFAULT_RECEIVE_DIR
    return text or DEFAULT_RECEIVE_DIR


def set_receive_dir(directory: str, cfg: Path | None = None) -> None:
    path = receive_file(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(directory.strip() or DEFAULT_RECEIVE_DIR)
