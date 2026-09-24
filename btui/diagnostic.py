"""Diagnostico de driver/hardware Bluetooth desde sysfs + BlueZ.

Sin datos de entorno hardcodeados: todo se lee en tiempo de ejecucion
(sysfs, bluetoothctl), para no filtrar identificadores reales en el repo.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_SYSFS = Path("/sys/class/bluetooth")


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def inspect_sysfs(root: Path = DEFAULT_SYSFS) -> list[dict[str, str]]:
    """Lista adaptadores hciX con driver y bus deducido del modalias."""
    hcis: list[dict[str, str]] = []
    if not root.is_dir():
        return hcis
    for hci in sorted(root.glob("hci*")):
        dev = hci / "device"
        driver_path = dev / "driver"
        driver = driver_path.resolve().name if driver_path.exists() else ""
        uevent = _read(dev / "uevent")
        product = ""
        for line in uevent.splitlines():
            if line.startswith("PRODUCT="):
                product = line.partition("=")[2]
                break
        modalias = _read(dev / "modalias")
        bus = ""
        if "usb:" in modalias:
            bus = "usb"
        elif "pci:" in modalias:
            bus = "pci"
        hcis.append(
            {
                "hci": hci.name,
                "address": _read(hci / "address"),
                "driver": driver,
                "bus": bus,
                "product": product,
                "modalias": modalias,
            }
        )
    return hcis


def parse_bluez_show(text: str) -> dict[str, str]:
    """Normaliza la salida multlinea de 'bluetoothctl show' a {campo: valor}.

    Tambien captura la MAC del header 'Controller AA:BB:CC:DD:EE:FF (public)'
    (en Alpine el sysfs puede no exponer hci/address).
    """
    fields: dict[str, str] = {}
    key: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("Controller "):
            fields["Controller"] = line.split()[1]
            key = None
            continue
        head, sep, rest = line.partition(": ")
        if sep and head.strip():
            key = head.strip()
            fields[key] = rest.split("\t")[0].strip()
        elif key:
            fields[key] += " " + line.strip()
    return fields


def render(hcis: list[dict[str, str]], show: dict[str, str]) -> str:
    lines: list[str] = []
    for h in hcis:
        lines.append(f"== {h['hci']} ==")
        lines.append(f"  direccion    {h['address'] or show.get('Controller') or '-'}")
        lines.append(f"  driver       {h['driver'] or '-'}")
        lines.append(f"  bus          {h['bus'] or '-'}")
        lines.append(f"  producto     {h['product'] or '-'}")
        lines.append(f"  powered      {show.get('Powered') or '-'}")
        lines.append(f"  discoverable {show.get('Discoverable') or '-'}")
        lines.append(f"  pairable     {show.get('Pairable') or '-'}")
        lines.append(f"  alias        {show.get('Alias') or '-'}")
    if not hcis:
        lines.append("sin adaptador hci (Bluetooth no disponible)")
    return "\n".join(lines)
