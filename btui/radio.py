"""Control de potencia (radio) del adaptador via bluetoothctl."""

import subprocess


def set_powered(on: bool) -> int:
    verb = "on" if on else "off"
    proc = subprocess.run(
        ["bluetoothctl", "power", verb],
        capture_output=True,
        text=True,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    return proc.returncode