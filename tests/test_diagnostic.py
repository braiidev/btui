from pathlib import Path

import pytest

from btui import diagnostic as diag

BLEUZ_SHOW = """Controller AA:BB:CC:DD:EE:FF (public)
	Name: BlueZ 5.85
	Alias: BlueZ 5.85
	Powered: yes
	DiscoverableTimeout: 0x00000000 (0)
	Discoverable: no
	Pairable: no
	UUID: PnP Information           (00001200-0000-1000-8000-00805f9b34fb)
	Modalias: usb:v1D6Bp0246d0555
"""


def test_parse_bluez_show() -> None:
    show = diag.parse_bluez_show(BLEUZ_SHOW)
    assert show["Powered"] == "yes"
    assert show["Discoverable"] == "no"
    assert show["Alias"] == "BlueZ 5.85"


@pytest.fixture
def fake_sysfs(tmp_path: Path) -> Path:
    hci = tmp_path / "hci0"
    dev = hci / "device"
    dev.mkdir(parents=True)
    (hci / "address").write_text("AA:BB:CC:DD:EE:FF")
    (dev / "uevent").write_text("PRODUCT=0a5c/219b/343\nDEVTYPE=usb_interface\n")
    (dev / "modalias").write_text("usb:v0A5Cp219Bd0343dcE0dsc01dp01icE0isc01ip01in00")
    drivers = tmp_path / "drivers"
    (drivers / "btusb").mkdir(parents=True)
    (dev / "driver").symlink_to(drivers / "btusb")
    return tmp_path


def test_inspect_sysfs(fake_sysfs: Path) -> None:
    hcis = diag.inspect_sysfs(fake_sysfs)
    assert len(hcis) == 1
    h = hcis[0]
    assert h["hci"] == "hci0"
    assert h["driver"] == "btusb"
    assert h["bus"] == "usb"
    assert h["product"] == "0a5c/219b/343"


def test_inspect_sysfs_sin_adaptador(tmp_path: Path) -> None:
    assert diag.inspect_sysfs(tmp_path) == []


def test_render(fake_sysfs: Path) -> None:
    hcis = diag.inspect_sysfs(fake_sysfs)
    show = diag.parse_bluez_show(BLEUZ_SHOW)
    out = diag.render(hcis, show)
    assert "== hci0 ==" in out
    assert "btusb" in out
    assert "powered      yes" in out
    assert "sin adaptador" not in out


def test_render_sin_adaptador() -> None:
    out = diag.render([], {})
    assert "sin adaptador hci" in out