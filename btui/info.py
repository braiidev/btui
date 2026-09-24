"""Diagnostico: informe de driver/hardware del adaptador."""

import subprocess

from btui import diagnostic as diag


def run() -> int:
    proc = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True)
    show = diag.parse_bluez_show(proc.stdout)
    print(diag.render(diag.inspect_sysfs(), show))
    return 0