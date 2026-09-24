"""Recepcion OPP: el host escucha pushes entrantes y los guarda en un directorio.

Corre como proceso foreground sobre la misma ObexSession privada de obex.py,
registra un agente org.bluez.obex.Agent1 que autoriza solo los equipos
conocidos+trusted y devuelve la ruta completa (leccion del desktop: devolver
solo carpeta hace que obexd concatene el Nombre y puede romperse).

La recepcion esta activa solo mientras el proceso corre (el bus privado cae al
salir): nada de aceptar pushes sin estar escuchando explicitamente.
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import MessageType
from dbus_next.errors import DBusError
from dbus_next.message import Message
from dbus_next.service import ServiceInterface, method

from btui import known, obex

if TYPE_CHECKING:
    o = str
    s = str

AGENT_PATH = "/btui/receive/agent"

OBEX_ERROR_REJECTED = "org.bluez.obex.Error.Rejected"


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


class ObexReceiveAgent(ServiceInterface):
    """Autoriza pushes solo de equipos conocidos+trusted, guardando en `root`."""

    def __init__(self, root: Path, bus: MessageBus) -> None:
        super().__init__("org.bluez.obex.Agent1")
        self._root = root
        self._bus = cast(Any, bus)

    @method()
    def Release(self) -> None:
        pass

    @method()
    def Cancel(self) -> None:
        pass

    async def _props(self, obj_path: str, iface: str) -> dict[str, Any]:
        reply = await self._bus.call(
            Message(
                destination=obex.OBEX_NAME,
                path=obj_path,
                interface=obex.PROPS_IFACE,
                member="GetAll",
                signature="s",
                body=[iface],
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise DBusError(str(reply.error_name), str(reply.body))
        return cast(dict, dict(reply.body[0] or {}))

    @method()
    async def AuthorizePush(self, transfer: "o") -> "s":
        props = await self._props(transfer, obex.TRANSFER_IFACE)
        proposed = _value(props.get("Filename"))
        session = _value(props.get("Session"))
        remote = None
        if session:
            try:
                sprops = await self._props(str(session), obex.SESSION_IFACE)
                remote = _value(sprops.get("Destination"))
            except DBusError:
                remote = None
        if remote and not known.is_trusted(str(remote)):
            raise DBusError(OBEX_ERROR_REJECTED, "equipo no confiado")
        name = "recibido.bin"
        if proposed and str(proposed):
            name = Path(str(proposed)).name
        return str(self._root / name)


async def _print_progress(bus: MessageBus, interval: float = 0.5) -> None:
    """Reporta Transferred/Size de cada transfer servidor activo."""
    last: dict[str, tuple[int | None, int | None]] = {}
    while True:
        try:
            reply = cast(
                Any,
                await bus.call(
                    Message(
                        destination=obex.OBEX_NAME,
                        path="/",
                        interface="org.freedesktop.DBus.ObjectManager",
                        member="GetManagedObjects",
                    )
                ),
            )
            objects = cast(dict, dict(reply.body[0] or {})) if reply.body else {}
        except Exception:
            objects = {}
        for obj_path, ifaces in objects.items():
            if not str(obj_path).startswith("/org/bluez/obex/server/"):
                continue
            transfer = ifaces.get(obex.TRANSFER_IFACE)
            if not isinstance(transfer, dict):
                continue
            transferred = obex._as_int(transfer.get("Transferred"))
            size = obex._as_int(transfer.get("Size"))
            status = _value(transfer.get("Status"))
            key = (transferred, size)
            if transferred is None or last.get(str(obj_path)) == key:
                continue
            last[str(obj_path)] = key
            pct = transferred * 100 // size if size else 0
            name = Path(obj_path).name
            line = f"[recibido {name}] {transferred}/{size or '?'} ({pct}%)"
            if status:
                line += f" {status}"
            print(line, file=sys.stderr, flush=True)
        await asyncio.sleep(interval)


async def _run_receive(root: Path, interval: float = 0.5) -> int:
    root.mkdir(parents=True, exist_ok=True)
    session = obex.ObexSession()
    await session.start(root=root)
    bus = session.bus
    bus.export(AGENT_PATH, ObexReceiveAgent(root, bus))
    reply = cast(
        Any,
        await bus.call(
            Message(
                destination=obex.OBEX_NAME,
                path=obex.OBEX_ROOT,
                interface="org.bluez.obex.AgentManager1",
                member="RegisterAgent",
                signature="o",
                body=[AGENT_PATH],
            )
        ),
    )
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(f"RegisterAgent: {reply.body}")

    stop = asyncio.Event()

    def on_signal(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    print(
        f"btui recibiendo en {root} (Ctrl-C para salir)",
        file=sys.stderr,
        flush=True,
    )
    try:
        task = asyncio.create_task(_print_progress(bus, interval))
        try:
            await stop.wait()
        finally:
            task.cancel()
    finally:
        await session.stop()
    return 0


def receive(directory: str) -> int:
    """Escucha pushes OPP y guarda en `directory`. 0 ok (salida limpia)."""
    obex.install_term_handlers()
    obex.reap_orphan_obexd()
    try:
        return asyncio.run(_run_receive(Path(directory)))
    except KeyboardInterrupt:
        print("recibo cancelado", file=sys.stderr)
        return 130


def run_receive(argv: list[str]) -> int:
    directory = argv[0] if argv else "."
    return receive(directory)
