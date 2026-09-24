"""Control de potencia y visibilidad del adaptador via bluetoothctl."""

import subprocess


def _bluetoothctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bluetoothctl", *args], capture_output=True, text=True)


def _show(proc: subprocess.CompletedProcess) -> None:
    text = proc.stdout.strip() or proc.stderr.strip()
    if text:
        print(text)


def set_powered(on: bool) -> int:
    proc = _bluetoothctl("power", "on" if on else "off")
    _show(proc)
    return proc.returncode


def set_alias(name: str) -> int:
    proc = _bluetoothctl("system-alias", name)
    _show(proc)
    return proc.returncode


def set_discoverable(on: bool, timeout: int | None = None) -> int:
    proc = _bluetoothctl("discoverable", "on" if on else "off")
    _show(proc)
    if on and timeout is not None:
        proc2 = _bluetoothctl("discoverable-timeout", str(timeout))
        _show(proc2)
        return proc2.returncode
    return proc.returncode


def set_pairable(on: bool) -> int:
    proc = _bluetoothctl("pairable", "on" if on else "off")
    _show(proc)
    return proc.returncode
