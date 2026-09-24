"""Persistencia de dispositivos conocidos en ~/.config/btui/devices.json.

La ruta de config respeta SUDO_USER (sudo la setea al escalar) para que el
mismo JSON lo lean usuarix y deamon sin partirse en /root.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def config_dir() -> Path:
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"
    home = Path(os.path.expanduser(f"~{user}"))
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(home / ".config")
    return Path(xdg) / "btui"


def known_file(cfg: Path | None = None) -> Path:
    return (cfg or config_dir()) / "devices.json"


def load(cfg: Path | None = None) -> list[dict]:
    path = known_file(cfg)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save(devices: list[dict], cfg: Path | None = None) -> Path:
    path = known_file(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(devices, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_known(
    mac: str, name: str, trusted: bool = True, cfg: Path | None = None
) -> list[dict]:
    devices = load(cfg)
    for dev in devices:
        if dev["mac"] == mac:
            dev["name"] = name or dev.get("name", "")
            dev["trusted"] = trusted
            save(devices, cfg)
            return devices
    devices.append(
        {"mac": mac, "name": name or "", "trusted": trusted, "added_at": _now()}
    )
    save(devices, cfg)
    return devices


def remove_known(mac: str, cfg: Path | None = None) -> bool:
    devices = load(cfg)
    before = len(devices)
    devices = [d for d in devices if d["mac"] != mac]
    if len(devices) != before:
        save(devices, cfg)
        return True
    return False


def set_trusted(mac: str, trusted: bool, cfg: Path | None = None) -> bool:
    devices = load(cfg)
    for dev in devices:
        if dev["mac"] == mac:
            dev["trusted"] = trusted
            save(devices, cfg)
            return True
    return False


def first_trusted(cfg: Path | None = None) -> str | None:
    """MAC del primer dispositivo conocido con trusted=True (destino por defecto)."""
    for dev in load(cfg):
        if dev.get("trusted"):
            return dev["mac"]
    return None
