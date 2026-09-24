"""Envio OPP (Object Push Profile) one-shot via obexd en un bus de sesion privado.

El host es headless: se levanta un dbus sesion propio, se lanza obexd ahi y se
habla con el usando Message D-Bus crudos (BlueZ no expone XMLIntrospection).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, cast

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import MessageType
from dbus_next.message import Message
from dbus_next.signature import Variant

from btui.known import config_dir

OBEX_NAME = "org.bluez.obex"
OBEX_ROOT = "/org/bluez/obex"
CLIENT_IFACE = "org.bluez.obex.Client1"
SESSION_IFACE = "org.bluez.obex.Session1"
TRANSFER_IFACE = "org.bluez.obex.Transfer1"
PUSH_IFACE = "org.bluez.obex.ObjectPush1"
PROPS_IFACE = "org.freedesktop.DBus.Properties"

ALPINE_OBEXD = "/usr/lib/bluetooth/obexd"
DEFAULT_TIMEOUT = 300
TRANSFER_COMPLETE = "complete"
TRANSFER_ERROR = "error"

ProgressFn = Callable[[int | None, int | None, str], None]


def _obexd_path() -> str | None:
    found = shutil.which("obexd")
    return found or (ALPINE_OBEXD if Path(ALPINE_OBEXD).exists() else None)


class ObexSession:
    """dbus-daemon de sesion privado + obexd conectado ahi."""

    def __init__(self) -> None:
        self._dbus: asyncio.subprocess.Process | None = None
        self._obexd: asyncio.subprocess.Process | None = None
        self._bus: MessageBus | None = None

    @property
    def ready(self) -> bool:
        return self._bus is not None

    @property
    def bus(self) -> MessageBus:
        if self._bus is None:
            raise RuntimeError("obex no iniciado")
        return self._bus

    async def start(self) -> str:
        runtime = config_dir() / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        daemon = _obexd_path()
        if daemon is None:
            raise RuntimeError("obexd no encontrado (instalar bluez-obexd)")

        self._dbus = await asyncio.create_subprocess_exec(
            "dbus-daemon",
            "--session",
            "--nofork",
            "--print-address",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if self._dbus.stdout is None:
            raise RuntimeError("dbus-daemon sin stdout")
        line = await self._dbus.stdout.readline()
        address = line.decode().strip()
        if not address:
            raise RuntimeError("dbus-daemon no emitio direccion de sesion")

        env = {
            **os.environ,
            "XDG_RUNTIME_DIR": str(runtime),
            "DBUS_SESSION_BUS_ADDRESS": address,
        }
        self._obexd = await asyncio.create_subprocess_exec(
            daemon,
            "-n",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        bus = MessageBus(bus_address=address)
        await bus.connect()
        self._bus = bus
        return address

    async def stop(self) -> None:
        for proc in (self._obexd, self._dbus):
            if proc is not None and proc.returncode is None:
                proc.terminate()
        for proc in (self._obexd, self._dbus):
            if proc is not None:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
        if self._bus is not None:
            self._bus.disconnect()
        self._obexd = None
        self._dbus = None
        self._bus = None


class ObexClient:
    """Cliente OPP sobre la sesion obex (Message D-Bus crudos)."""

    def __init__(self, session: ObexSession) -> None:
        self._session = session

    def _call(self) -> Any:
        return cast(Any, self._session.bus)

    async def message(
        self,
        path: str,
        iface: str,
        member: str,
        body: list[Any] | None = None,
        signature: str = "",
    ) -> Any:
        reply = await self._call().call(
            Message(
                destination=OBEX_NAME,
                path=path,
                interface=iface,
                member=member,
                signature=signature,
                body=body or [],
            )
        )
        if reply.message_type == MessageType.ERROR:
            detail = str(reply.body[0]) if reply.body else member
            raise RuntimeError(f"{member}: {detail}")
        return reply.body[0] if reply.body else None

    async def create_session(self, address: str) -> str:
        path = await self.message(
            OBEX_ROOT,
            CLIENT_IFACE,
            "CreateSession",
            [address, {"Target": Variant("s", "opp")}],
            "sa{sv}",
        )
        return str(path)

    async def remove_session(self, session_path: str) -> None:
        await self.message(session_path, SESSION_IFACE, "Remove")

    async def send_file(self, session_path: str, file: str) -> str:
        path = await self.message(
            session_path,
            PUSH_IFACE,
            "SendFile",
            [file],
            "s",
        )
        return str(path)

    async def transfer_status(self, transfer_path: str) -> Any:
        return await self.message(
            transfer_path,
            PROPS_IFACE,
            "Get",
            [TRANSFER_IFACE, "Status"],
            "ss",
        )

    async def transfer_properties(self, transfer_path: str) -> dict[str, Any]:
        props = await self.message(
            transfer_path,
            PROPS_IFACE,
            "GetAll",
            [TRANSFER_IFACE],
            "s",
        )
        return dict(props or {})


def _value(value: Any) -> Any:
    return value.value if isinstance(value, Variant) else value


def _as_int(value: Any) -> int | None:
    value = _value(value)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


_MAX_POLL_ERRORS = 3


async def wait_transfer(
    bus: MessageBus,
    transfer_path: str,
    transfer_file: str,
    progress: ProgressFn | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    client: ObexClient | None = None,
    interval: float = 0.5,
) -> bool:
    """Espera la transferencia sondeando GetAll; True si completo, False si error.

    obexd de este host desregistra el objeto Transfer ni bien finaliza (a los
    microsegundos del ultimo byte) y no entrega la senal terminal fielmente.
    Entonces: si ya se transfirio Size bytes (>0) y el objeto desaparece, se
    asume exito. Un error de Get antes de llegar a Size es fallo duro.
    """

    if client is None:
        raise RuntimeError("wait_transfer requiere client")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    errors = 0
    transferred_all = False
    while True:
        try:
            props = await client.transfer_properties(transfer_path)
        except asyncio.CancelledError:
            raise
        except Exception:
            errors += 1
            if errors > _MAX_POLL_ERRORS:
                if transferred_all:
                    return True
                raise RuntimeError(
                    f"transferencia {Path(transfer_file).name}: obexd dejo de responder"
                )
        else:
            errors = 0
            status = _value(props.get("Status"))
            transferred = _as_int(props.get("Transferred"))
            size = _as_int(props.get("Size"))
            if progress is not None and transferred is not None:
                progress(transferred, size, transfer_file)
            if status == TRANSFER_COMPLETE:
                return True
            if status == TRANSFER_ERROR:
                return False
            if transferred is not None and size and transferred >= size:
                transferred_all = True
        if loop.time() >= deadline:
            raise RuntimeError(
                f"transferencia {Path(transfer_file).name} cancelada por timeout"
            )
        await asyncio.sleep(interval)


def _print_progress(transferred: int | None, size: int | None, name: str) -> None:
    if transferred is None:
        return
    if size:
        pct = transferred * 100 // size
    else:
        pct = 0
    print(f"\r[{name}] {transferred}/{size or '?'} ({pct}%)", end="", file=sys.stderr)


async def _run_send(
    files: list[str], address: str, progress: ProgressFn | None = None
) -> bool:
    session = ObexSession()
    await session.start()
    try:
        client = ObexClient(session)
        session_path = await client.create_session(address)
        for file in files:
            transfer_path = await client.send_file(session_path, file)
            ok = await wait_transfer(
                session.bus,
                transfer_path,
                Path(file).name,
                progress=progress,
                client=client,
            )
            if not ok:
                print(
                    f"\nerror: transferencia de {Path(file).name} fallo",
                    file=sys.stderr,
                )
                return False
        return True
    finally:
        await session.stop()


def send(files: list[str], address: str) -> int:
    """Envia archivos por OPP a `address`. 0 ok, 1 error."""

    paths = [(file, Path(file)) for file in files]
    for file, path in paths:
        if not path.is_file():
            print(f"error: no existe el archivo: {file}", file=sys.stderr)
            return 1
    try:
        ok = asyncio.run(
            _run_send([str(p) for _, p in paths], address, _print_progress)
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if ok:
        print("\nenvio completo", file=sys.stderr)
        return 0
    return 1
