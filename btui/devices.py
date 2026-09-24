"""Operaciones one-shot sobre dispositivos (buscar, parear, confiar, olvidar)."""

from __future__ import annotations

import subprocess
import time

from btui import known


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True)


def parse_devices(text: str) -> list[dict]:
    devices: list[dict] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0] == "Device":
            mac = parts[1]
            name = " ".join(parts[2:]) if len(parts) > 2 else ""
            devices.append({"mac": mac, "name": name})
    return devices


def scan(timeout: int = 6) -> list[dict]:
    _run("bluetoothctl", "start", "discovery")
    time.sleep(timeout)
    res = _run("bluetoothctl", "devices")
    _run("bluetoothctl", "stop", "discovery")
    return parse_devices(res.stdout)


def device_name(mac: str) -> str:
    res = _run("bluetoothctl", "info", mac)
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            return line.split(":", 1)[1].strip()
    return ""


def pair(mac: str) -> int:
    code = _run("bluetoothctl", "pair", mac).returncode
    _run("bluetoothctl", "trust", mac)
    known.add_known(mac, device_name(mac))
    return code


def accept(mac: str) -> int:
    _run("bluetoothctl", "trust", mac)
    known.add_known(mac, device_name(mac))
    return 0


def deny(mac: str) -> int:
    _run("bluetoothctl", "untrust", mac)
    known.remove_known(mac)
    return 0


def run_cli(action: str, mac: str | None) -> int:
    if action == "list":
        for dev in known.load():
            state = "trusted" if dev.get("trusted") else "known"
            print(f"{dev['mac']}\t{dev.get('name', '')}\t{state}")
        return 0
    if action == "search":
        for dev in scan():
            print(f"{dev['mac']}\t{dev['name']}")
        return 0
    if action == "pair" and mac:
        return pair(mac)
    if action == "accept" and mac:
        return accept(mac)
    if action == "deny" and mac:
        return deny(mac)
    print("uso: --devices list|search|pair <mac>|accept <mac>|deny <mac>")
    return 2