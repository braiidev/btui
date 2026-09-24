from btui import tui


def test_adapter_lines_usa_sysfs_y_show():
    show = {
        "Controller": "AA:BB:CC:DD:EE:FF",
        "Alias": "miniserver",
        "Powered": "yes",
        "Discoverable": "no",
        "Pairable": "yes",
    }
    hcis = [
        {"hci": "hci0", "address": "AA:BB:CC:DD:EE:FF", "driver": "btusb", "bus": "usb"}
    ]
    lines = tui.adapter_lines(show, hcis)
    text = "\n".join(lines)
    assert "hci0" in text
    assert "miniserver" in text
    assert "btusb (usb)" in text
    assert "powered      yes" in text


def test_adapter_lines_fallback_sin_hci():
    show = {"Controller": "AA:BB:CC:DD:EE:FF", "Powered": "yes"}
    lines = tui.adapter_lines(show, [])
    assert "Adaptador  -  AA:BB:CC:DD:EE:FF" in lines[0]
    assert "driver       - (-)" in lines[-1]


def test_device_lines_marca_trusted_y_known():
    devices = [
        {"mac": "11:11:11:11:11:11", "name": "telefono", "trusted": True},
        {"mac": "22:22:22:22:22:22", "name": "", "trusted": False},
    ]
    lines = tui.device_lines(devices, known_macs={"22:22:22:22:22:22"})
    assert lines[0].startswith("  * 11:11:11:11:11:11")
    assert "[trusted]" in lines[0]
    assert "[known]" in lines[1]
    assert "  -" in lines[1]


def test_screen_lines_oculta_cercanos_si_none():
    lines = tui.screen_lines({}, [], [], None, "")
    text = "\n".join(lines)
    assert "Conocidos (0)" in text
    assert "(ninguno)" in text
    assert "Cercanos" not in text
    assert tui.HELP in text


def test_screen_lines_muestra_cercanos_y_mensaje():
    known_devs = [{"mac": "11:11:11:11:11:11", "name": "x", "trusted": True}]
    nearby = [
        {"mac": "11:11:11:11:11:11", "name": "x"},
        {"mac": "33:33:33:33:33:33", "name": "nuevo"},
    ]
    lines = tui.screen_lines({}, [], known_devs, nearby, "descubrimiento: 2")
    text = "\n".join(lines)
    assert "Cercanos (2)" in text
    assert "descubrimiento: 2" in text
    assert "33:33:33:33:33:33" in text
    assert tui.HELP not in text


class _FakeStdout:
    def isatty(self) -> bool:
        return False


def test_run_sin_tty_devuelve_error(monkeypatch, capsys):
    monkeypatch.setattr(tui.sys, "stdout", _FakeStdout())
    assert tui.run() == 1
    assert "requiere una terminal" in capsys.readouterr().err
