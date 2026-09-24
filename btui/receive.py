"""Recepcion OPP: el host escucha pushes entrantes y los guarda en un directorio.

Corre como proceso foreground sobre la misma ObexSession privada de obex.py,
registra un agente org.bluez.obex.Agent1 que autoriza solo los equipos
conocidos+trusted y devuelve la ruta completa (leccion del desktop: devolver
solo carpeta hace que obexd concatene el Nombre y puede romperse).

La recepcion esta activa solo mientras el proceso corre (el bus privado cae al
salir): nada de aceptar pushes sin estar escuchando explicitamente.
"""

import asyncio
import select
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

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
FALLBACK_NAME = "recibido.bin"
PROMPT_TIMEOUT = 60
KNOWN_YES = {"a", "s", "y", ""}
KNOWN_NO = {"c", "n", "q", "x", "no", "cancelar"}


def _choice(text: str) -> bool | None:
    """True acepta, False rechaza, None vuelve a preguntar."""
    choice = str(text).strip().lower()
    if choice in KNOWN_YES:
        return True
    if choice in KNOWN_NO:
        return False
    return None


def _ask_accept(remote: str, filename: str, display_name: str) -> bool:
    """Prompt interactivo en el terminal donde corre `--receive` (foreground)."""
    prompt = (
        f"[push] «{display_name}» ({remote}) envia "
        f"'{filename or 'archivo'}': aceptar [a] / cancelar [c] "
    )
    while True:
        print(prompt, end="", file=sys.stderr, flush=True)
        ready, _, _ = select.select([sys.stdin], [], [], PROMPT_TIMEOUT)
        if not ready:
            print(" (timeout, rechazado)", file=sys.stderr, flush=True)
            return False
        line = sys.stdin.readline()
        decision = _choice(line)
        if decision is True:
            print("aceptado", file=sys.stderr, flush=True)
            return True
        if decision is False:
            print("rechazado", file=sys.stderr, flush=True)
            return False
        print("?", end="", file=sys.stderr, flush=True)


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    for i in range(1, 100):
        cand = target.with_name(f"{target.stem} ({i}){target.suffix}")
        if not cand.exists():
            return cand
    return target


def finalize_file(root: Path, target: Path, proposed: str) -> Path | None:
    """Devuelve la ruta final tras (re)nombrar segun `proposed`.

    obexd completa `Filename` recien al autorizar en muchos telefonos; por eso
    se guarda con el nombre propuesto en ese momento (o `recibido.bin`) y aca,
    al completar, se renombra al nombre real evitando colisiones. None si no
    quedo archivo.
    """
    if not target.exists():
        return None
    if not proposed:
        return target
    final = _unique_path(root / Path(str(proposed)).name)
    if target != final:
        target.rename(final)
    return final if final.exists() else None


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


class ObexReceiveAgent(ServiceInterface):
    """Autoriza pushes (trusted o por prompt) y guarda en `root`.

    `on_done` recibe los archivos ya renombrados y se usa para anunciar.
    """

    def __init__(
        self,
        root: Path,
        bus: MessageBus,
        on_done: Callable[[Path, int | None, str | None], None] | None = None,
    ) -> None:
        super().__init__("org.bluez.obex.Agent1")
        self._root = root
        self._bus = cast(Any, bus)
        self.on_done = on_done
        self._targets: dict[str, str] = {}

    @method()
    def Release(self) -> None:
        pass

    @method()
    def Cancel(self) -> None:
        pass

    def authorize_target(self, transfer_path: str) -> str | None:
        return self._targets.get(transfer_path)

    def forget(self, transfer_path: str) -> None:
        self._targets.pop(transfer_path, None)

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
        name = FALLBACK_NAME
        if proposed and str(proposed):
            name = Path(str(proposed)).name
        if remote and not known.is_trusted(str(remote)):
            if not sys.stdin.isatty():
                raise DBusError(OBEX_ERROR_REJECTED, "equipo no confiado")
            display = next(
                (
                    d.get("name") or ""
                    for d in known.load()
                    if str(d.get("mac", "")).lower() == str(remote).lower()
                ),
                "",
            )
            loop = asyncio.get_running_loop()
            accepted = await loop.run_in_executor(
                None, _ask_accept, str(remote), name, display or str(remote)
            )
            if not accepted:
                raise DBusError(OBEX_ERROR_REJECTED, "equipo no confiado")
        target = str(self._root / name)
        self._targets[str(transfer)] = target
        return target


def _show_completed(final: Path, size: int | None, target: str | None) -> None:
    line = f"recibido: {final} ({size or '?'} bytes)"
    if target and final.name != Path(target).name:
        line = f"recibido: {final.name} (era {Path(target).name}) ({size or '?'} bytes)"
    print(line, file=sys.stderr, flush=True)


async def _monitor(
    bus: MessageBus,
    agent: ObexReceiveAgent,
    root: Path,
    interval: float = 0.5,
) -> None:
    """Sondea transfers del servidor: reporta progreso y finaliza cada push.

    Al completar (Status=complete o el objeto desaparece tras transferir) y si
    obexd ya entrego `Filename`, renombra el archivo al nombre real y avisa.
    """
    last: dict[str, tuple[int | None, int | None, str | None]] = {}
    finalized: set[str] = set()
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
        present: set[str] = set()
        for obj_path, ifaces in objects.items():
            if not str(obj_path).startswith("/org/bluez/obex/server/"):
                continue
            transfer = ifaces.get(obex.TRANSFER_IFACE)
            if not isinstance(transfer, dict):
                continue
            transferred = obex._as_int(transfer.get("Transferred"))
            size = obex._as_int(transfer.get("Size"))
            status = _value(transfer.get("Status"))
            filename = str(_value(transfer.get("Filename")) or "")
            key = str(obj_path)
            present.add(key)
            if status == obex.TRANSFER_COMPLETE and key not in finalized:
                finalized.add(key)
                target = agent.authorize_target(key)
                if target:
                    final = finalize_file(root, Path(target), filename)
                    if final is not None and agent.on_done is not None:
                        agent.on_done(final, size, target)
                agent.forget(key)
                continue
            if transferred is None or last.get(key) == (transferred, size, status):
                continue
            last[key] = (transferred, size, status)
            pct = transferred * 100 // size if size else 0
            name = Path(key).name
            line = f"[recibido {name}] {transferred}/{size or '?'} ({pct}%)"
            if status:
                line += f" {status}"
            print(line, file=sys.stderr, flush=True)
        for gone in [
            key for key in last if key not in present and key not in finalized
        ]:
            finalized.add(gone)
            transferred, size, _status = last[gone]
            if transferred is not None and (size is None or transferred >= (size or 0)):
                target = agent.authorize_target(gone)
                if target:
                    final = finalize_file(root, Path(target), "")
                    if final is not None and agent.on_done is not None:
                        agent.on_done(final, size, target)
            agent.forget(gone)
        await asyncio.sleep(interval)


async def _run_receive(root: Path, interval: float = 0.5) -> int:
    root.mkdir(parents=True, exist_ok=True)
    session = obex.ObexSession()
    await session.start(root=root)
    bus = session.bus
    agent = ObexReceiveAgent(root, bus, on_done=_show_completed)
    bus.export(AGENT_PATH, agent)
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
        task = asyncio.create_task(_monitor(bus, agent, root, interval))
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
