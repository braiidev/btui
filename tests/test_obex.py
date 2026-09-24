import asyncio
import shutil

import pytest
from dbus_next import Message, MessageType, Variant

from btui import cli, obex

NEEDS_DBUS = pytest.mark.skipif(
    shutil.which("dbus-daemon") is None or not obex._obexd_path(),
    reason="dbus-daemon u obexd ausentes",
)


class FakeReply:
    def __init__(self, body=None, error=None):
        self.message_type = MessageType.ERROR if error else MessageType.METHOD_RETURN
        self.body = [error] if error else (body if body is not None else [])


class FakeBus:
    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.calls = []
        self.handlers = []

    def add_message_handler(self, handler):
        self.handlers.append(handler)

    def remove_message_handler(self, handler):
        if handler in self.handlers:
            self.handlers.remove(handler)

    async def call(self, msg: Message):
        self.calls.append(msg)
        if not self.replies:
            raise AssertionError("sin reply programado: " + msg.member)
        return self.replies.pop(0)


class FakeSession:
    def __init__(self, bus):
        self._bus = bus

    @property
    def ready(self):
        return True

    @property
    def bus(self):
        return self._bus


def test_client_sin_sesion_error():
    client = obex.ObexClient(obex.ObexSession())
    with pytest.raises(RuntimeError, match="obex no iniciado"):
        asyncio.run(client.create_session("00:11:22:33:44:55"))


def test_create_session_envia_message_correcto():
    bus = FakeBus([FakeReply(["/org/bluez/obex/client/session1"])])
    session = FakeSession(bus)
    client = obex.ObexClient(session)
    path = asyncio.run(client.create_session("40:ec:99:a2:3b:b2"))
    assert path == "/org/bluez/obex/client/session1"
    msg = bus.calls[0]
    assert msg.destination == "org.bluez.obex"
    assert msg.interface == "org.bluez.obex.Client1"
    assert msg.member == "CreateSession"
    assert msg.signature == "sa{sv}"
    assert msg.body[0] == "40:ec:99:a2:3b:b2"
    assert msg.body[1]["Target"].value == "opp"


def test_send_file_message():
    bus = FakeBus([FakeReply(["t0"])])
    session = FakeSession(bus)
    client = obex.ObexClient(session)
    path = asyncio.run(client.send_file("/org/bluez/obex/client/s1", "/tmp/a.txt"))
    assert path == "t0"
    msg = bus.calls[0]
    assert msg.interface == "org.bluez.obex.ObjectPush1"
    assert msg.member == "SendFile"
    assert msg.body == ["/tmp/a.txt"]


def test_error_reply_levanta_runtime():
    bus = FakeBus([FakeReply(error="org.bluez.SessionFailed")])
    session = FakeSession(bus)
    client = obex.ObexClient(session)
    with pytest.raises(RuntimeError, match="CreateSession"):
        asyncio.run(client.create_session("00:11:22:33:44:55"))


def test_wait_transfer_completa_con_progresso():
    bus = FakeBus(
        [
            FakeReply(
                [
                    {
                        "Status": Variant("s", "active"),
                        "Transferred": Variant("t", 42),
                        "Size": Variant("t", 100),
                    }
                ]
            ),
            FakeReply(
                [
                    {
                        "Status": Variant("s", "complete"),
                        "Transferred": Variant("t", 100),
                        "Size": Variant("t", 100),
                    }
                ]
            ),
        ]
    )
    session = FakeSession(bus)
    client = obex.ObexClient(session)
    progress = []

    async def run():
        return await obex.wait_transfer(
            bus,
            "/org/bluez/obex/client/transfer1",
            "a.txt",
            progress=lambda t, s, name: progress.append((t, name)),
            client=client,
            interval=0.01,
        )

    assert asyncio.run(run()) is True
    assert progress == [(42, "a.txt"), (100, "a.txt")]


def test_wait_transfer_detecta_ya_completo_por_poll():
    bus = FakeBus([FakeReply([{"Status": Variant("s", "complete")}])])
    session = FakeSession(bus)
    client = obex.ObexClient(session)

    async def run():
        return await obex.wait_transfer(
            bus,
            "/org/bluez/obex/client/transfer1",
            "a.txt",
            client=client,
            interval=0.01,
        )

    assert asyncio.run(run()) is True


def test_wait_transfer_en_error_devuelve_false():
    bus = FakeBus([FakeReply([{"Status": Variant("s", "error")}])])
    session = FakeSession(bus)
    client = obex.ObexClient(session)

    async def run():
        return await obex.wait_transfer(
            bus,
            "/org/bluez/obex/client/transfer1",
            "a.txt",
            client=client,
            interval=0.01,
        )

    assert asyncio.run(run()) is False


def test_wait_transfer_timeout_levanta_runtimeerror():
    bus = FakeBus([FakeReply([{"Status": Variant("s", "active")}]) for _ in range(20)])
    session = FakeSession(bus)
    client = obex.ObexClient(session)

    async def run():
        await obex.wait_transfer(
            bus,
            "/org/bluez/obex/client/transfer1",
            "a.txt",
            client=client,
            interval=0.01,
            timeout=0.05,
        )

    with pytest.raises(RuntimeError, match="timeout"):
        asyncio.run(run())


def test_wait_transfer_sin_client_error():
    with pytest.raises(RuntimeError, match="requiere client"):
        asyncio.run(obex.wait_transfer(FakeBus(), "/t", "a.txt"))


class FakeBusFail:
    def __init__(self, replies, fail_after):
        self.replies = list(replies)
        self.fail_after = fail_after
        self.calls = 0

    async def call(self, msg):
        self.calls += 1
        if self.calls > self.fail_after:
            raise RuntimeError("No such object")
        return self.replies[self.calls - 1]


class FakeSessionFail:
    def __init__(self, bus):
        self._bus = bus

    @property
    def ready(self):
        return True

    @property
    def bus(self):
        return self._bus


def test_wait_transfer_100pct_luego_objeto_desaparece_es_ok():
    bus = FakeBusFail(
        [
            FakeReply(
                [
                    {
                        "Status": Variant("s", "active"),
                        "Transferred": Variant("t", 22),
                        "Size": Variant("t", 22),
                    }
                ]
            ),
        ],
        fail_after=1,
    )
    session = FakeSessionFail(bus)
    client = obex.ObexClient(session)

    async def run():
        return await obex.wait_transfer(
            bus,
            "/org/bluez/obex/client/transfer1",
            "a.txt",
            client=client,
            interval=0.01,
        )

    assert asyncio.run(run()) is True


def test_wait_transfer_objeto_desaparece_sin_100pct_es_error():
    bus = FakeBusFail(
        [
            FakeReply(
                [
                    {
                        "Status": Variant("s", "active"),
                        "Transferred": Variant("t", 5),
                        "Size": Variant("t", 100),
                    }
                ]
            ),
        ],
        fail_after=1,
    )
    session = FakeSessionFail(bus)
    client = obex.ObexClient(session)

    async def run():
        await obex.wait_transfer(
            bus,
            "/org/bluez/obex/client/transfer1",
            "a.txt",
            client=client,
            interval=0.01,
        )

    with pytest.raises(RuntimeError, match="dejo de responder"):
        asyncio.run(run())


def test_transfer_properties_getall():
    bus = FakeBus([FakeReply([{"Status": Variant("s", "active")}])])
    session = FakeSession(bus)
    client = obex.ObexClient(session)
    props = asyncio.run(client.transfer_properties("/org/bluez/obex/client/transfer1"))
    assert props == {"Status": Variant("s", "active")}
    msg = bus.calls[0]
    assert msg.interface == "org.freedesktop.DBus.Properties"
    assert msg.member == "GetAll"


def test_cli_send_routing_usa_primer_trusted(monkeypatch):
    from btui import known

    monkeypatch.setattr(known, "first_trusted", lambda: "40:EC:99:A2:3B:B2")
    calls = []
    monkeypatch.setattr(
        obex, "send", lambda files, mac: calls.append((files, mac)) or 0
    )
    assert cli.run(["--send", "/tmp/a.txt", "/tmp/b.txt"]) == 0
    assert calls == [(["/tmp/a.txt", "/tmp/b.txt"], "40:EC:99:A2:3B:B2")]


def test_cli_send_explicit_to(monkeypatch):
    calls = []
    monkeypatch.setattr(
        obex, "send", lambda files, mac: calls.append((files, mac)) or 0
    )
    assert cli.run(["--send", "/tmp/a.txt", "--to", "AA:BB:CC:DD:EE:FF"]) == 0
    assert calls == [(["/tmp/a.txt"], "AA:BB:CC:DD:EE:FF")]


def test_cli_send_sin_destino_error(monkeypatch, capsys):
    from btui import known

    monkeypatch.setattr(known, "first_trusted", lambda: None)
    assert cli.run(["--send", "/tmp/a.txt"]) == 1
    assert "sin destino" in capsys.readouterr().err


def test_send_valida_archivos(capsys):
    assert obex.send(["/no/existe/archivo.txt"], "00:11:22:33:44:55") == 1
    assert "no existe el archivo" in capsys.readouterr().err
