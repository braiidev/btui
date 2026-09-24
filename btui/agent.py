"""Agente de pareado BlueZ (NoInputNoOutput) registrado por el daemon.

Acepta automaticamente pairings 'just-works' entrantes en un host headless.
Los PIN clasicos (KeyboardDisplay) se manejan en la TUI (v0.8/0.9).

Nota: NO usar `from __future__ import annotations` aqui: dbus-next 0.2.x
stringifica `-> None` y falla al registrar metodos sin retorno.
"""

import asyncio
from typing import TYPE_CHECKING, Any, cast

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import BusType
from dbus_next.service import ServiceInterface, method

if TYPE_CHECKING:
    o = str
    s = str
    u = int

AGENT_PATH = "/btui/agent"
AGENT_IFACE = "org.bluez.Agent1"
AGENT_CAPABILITY = "NoInputNoOutput"
BLUEZ_NAME = "org.bluez"

# BlueZ no expone XMLIntrospection en runtime: hay que pasarle el XML del
# AgentManager1 a dbus-next 0.2.x para poder usar get_proxy_object.
AGENT_MANAGER_INTROSPECTION = """<node>
  <interface name="org.bluez.AgentManager1">
    <method name="RegisterAgent">
      <arg type="o" name="agent" direction="in"/>
      <arg type="s" name="capability" direction="in"/>
    </method>
    <method name="UnregisterAgent">
      <arg type="o" name="agent" direction="in"/>
    </method>
    <method name="RequestDefaultAgent">
      <arg type="o" name="agent" direction="in"/>
    </method>
  </interface>
</node>"""


class BtuiAgent(ServiceInterface):
    """Auto-acepta pedidos de pareado sin interaccion (NoInputNoOutput)."""

    def __init__(self) -> None:
        super().__init__(AGENT_IFACE)

    @method()
    def Release(self) -> None:
        pass

    @method()
    def RequestPinCode(self, device: "o") -> "s":
        return ""

    @method()
    def RequestPasskey(self, device: "o") -> "u":
        return 0

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u") -> None:
        pass

    @method()
    def RequestAuthorization(self, device: "o") -> None:
        pass

    @method()
    def AuthorizeService(self, device: "o", uuid: "s") -> None:
        pass

    @method()
    def Cancel(self) -> None:
        pass


async def register_agent(
    bus: MessageBus,
    path: str = AGENT_PATH,
    capability: str = AGENT_CAPABILITY,
    agent_cls=BtuiAgent,
) -> None:
    """Exporta el agente en el system bus y lo registra como default en BlueZ."""
    bus.export(path, agent_cls())
    bus_any = cast(Any, bus)
    manager = bus_any.get_proxy_object(
        BLUEZ_NAME, "/org/bluez", AGENT_MANAGER_INTROSPECTION
    )
    iface = cast(Any, manager.get_interface("org.bluez.AgentManager1"))
    await iface.call_register_agent(path, capability)
    await iface.call_request_default_agent(path)


def run_agent_thread() -> None:
    """Bucle asyncio del agente en un hilo daemon; vive mientras el daemon.

    Se ejecuta como hilo del proceso `btui daemon`, sobre el system bus.
    """

    async def _main() -> None:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        await register_agent(bus)
        while True:
            await asyncio.sleep(3600)

    asyncio.run(_main())
