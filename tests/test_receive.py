import asyncio
import os
from pathlib import Path

import pytest
from dbus_next import Variant
from dbus_next.constants import MessageType
from dbus_next.errors import DBusError

from btui import cli, known, obex, receive


def _proc_entry(root: Path, pid: int, cmd0: str, uid: int, ppid: int) -> None:
    d = root / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cmdline").write_bytes(cmd0.encode() + b"\0")
    (d / "status").write_text(f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\nPPid:\t{ppid}\n")


def test_reap_orphan_obexd_mata_solo_huerfanos_del_usuario(
    tmp_path, monkeypatch, capsys
):
    _proc_entry(
        tmp_path, os.getpid(), "/usr/lib/bluetooth/obexd", os.getuid(), 1
    )  # self, no tocar
    _proc_entry(
        tmp_path, 111, "/usr/lib/bluetooth/obexd", os.getuid(), 1
    )  # huerfano mio -> reapar
    _proc_entry(
        tmp_path, 222, "/usr/lib/bluetooth/obexd", os.getuid(), 555
    )  # activo, no tocar
    _proc_entry(
        tmp_path, 333, "/usr/lib/bluetooth/obexd", os.getuid() + 999, 1
    )  # otro user
    kills = []
    monkeypatch.setattr(obex.os, "kill", lambda pid, sig: kills.append(pid))
    reaped = obex.reap_orphan_obexd(tmp_path)
    assert reaped == [111]
    assert kills == [111]
    assert capsys.readouterr().err.startswith("obexd huerfano(s) reap")


def test_reap_no_crash_con_proc_sucio(tmp_path, capsys):
    (tmp_path / "9999").mkdir()
    (tmp_path / "9999" / "cmdline").write_bytes(b"")
    (tmp_path / "notapid").mkdir()
    (tmp_path / "notapid" / "cmdline").write_bytes(b"x\0")
    assert obex.reap_orphan_obexd(tmp_path) == []
    assert capsys.readouterr().err == ""


class FakeReply:
    def __init__(self, body=None, error=None, error_name=None):
        self.message_type = (
            MessageType.ERROR if error is not None else MessageType.METHOD_RETURN
        )
        self.body = [error] if error is not None else (body if body is not None else [])
        self.error_name = error_name


class FakeBus:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def call(self, msg):
        self.calls.append((msg.path, msg.member))
        if not self.replies:
            raise AssertionError("sin reply programado: " + msg.member)
        return self.replies.pop(0)


def _run_authorize(agent, transfer="/org/bluez/obex/server/s1/t1"):
    meth = receive.ObexReceiveAgent.AuthorizePush.__dict__["__DBUS_METHOD"]
    return asyncio.run(meth.fn(agent, transfer))


def test_authorize_push_trusted_devuelve_ruta(monkeypatch):
    monkeypatch.setattr(
        known,
        "load",
        lambda cfg=None: [{"mac": "40:EC:99:A2:3B:B2", "trusted": True}],
    )
    bus = FakeBus(
        [
            FakeReply(
                [
                    {
                        "Session": Variant("o", "/org/bluez/obex/server/s1"),
                        "Filename": Variant("s", "/recv/archivo.txt"),
                    }
                ]
            ),
            FakeReply(
                [
                    {
                        "Source": Variant("s", "50:63:13:D1:1A:A3"),
                        "Destination": Variant("s", "40:EC:99:A2:3B:B2"),
                    }
                ]
            ),
        ]
    )
    agent = receive.ObexReceiveAgent(Path("/tmp/recibido"), bus)
    assert _run_authorize(agent) == "/tmp/recibido/archivo.txt"
    assert bus.calls == [
        ("/org/bluez/obex/server/s1/t1", "GetAll"),
        ("/org/bluez/obex/server/s1", "GetAll"),
    ]


def test_authorize_push_rechaza_no_trusted(monkeypatch, tmp_path):
    monkeypatch.setattr(known, "load", lambda cfg=None: [])
    bus = FakeBus(
        [
            FakeReply(
                [
                    {
                        "Session": Variant("o", "/org/bluez/obex/server/s1"),
                        "Filename": Variant("s", "/recv/archivo.txt"),
                    }
                ]
            ),
            FakeReply([{"Destination": Variant("s", "11:22:33:44:55:66")}]),
        ]
    )
    agent = receive.ObexReceiveAgent(tmp_path, bus)
    with pytest.raises(DBusError) as exc:
        _run_authorize(agent)
    assert exc.value.type == receive.OBEX_ERROR_REJECTED


def test_authorize_push_sin_destination_acepta():
    bus = FakeBus(
        [
            FakeReply(
                [
                    {
                        "Session": Variant("o", "/org/bluez/obex/server/s1"),
                        "Filename": Variant("s", "/recv/archivo.txt"),
                    }
                ]
            ),
            FakeReply([{"Destination": Variant("s", "")}]),
        ]
    )
    agent = receive.ObexReceiveAgent(Path("/tmp/recibido"), bus)
    assert _run_authorize(agent) == "/tmp/recibido/archivo.txt"


def test_authorize_push_sin_filename_fallback():
    bus = FakeBus(
        [
            FakeReply([{"Session": Variant("o", "/org/bluez/obex/server/s1")}]),
            FakeReply([{"Destination": Variant("s", "")}]),
        ]
    )
    agent = receive.ObexReceiveAgent(Path("/tmp/recibido"), bus)
    assert _run_authorize(agent) == "/tmp/recibido/recibido.bin"


def test_known_is_trusted(tmp_path):
    cfg = tmp_path / "devices.json"
    assert known.is_trusted("aa:bb:cc:dd:ee:ff", cfg) is False
    known.add_known("AA:BB:CC:DD:EE:FF", "x", trusted=True, cfg=cfg)
    assert known.is_trusted("aa:bb:cc:dd:ee:ff", cfg) is True


def test_cli_receive_routing(monkeypatch):
    calls = []
    monkeypatch.setattr(
        receive, "receive", lambda directory: calls.append(directory) or 0
    )
    assert cli.run(["--receive", "/tmp/inbox"]) == 0
    assert calls == ["/tmp/inbox"]
