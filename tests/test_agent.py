import asyncio

from btui import agent as agent_mod


class FakeManagerIface:
    def __init__(self, calls):
        self.calls = calls

    async def call_register_agent(self, path, capability):
        self.calls.append(("register", path, capability))

    async def call_request_default_agent(self, path):
        self.calls.append(("default", path))


class FakeProxy:
    def __init__(self, calls):
        self.calls = calls

    def get_interface(self, name):
        assert name == "org.bluez.AgentManager1"
        return FakeManagerIface(self.calls)


class FakeBus:
    def __init__(self):
        self.calls = []
        self.exported = []

    def export(self, path, obj):
        self.exported.append((path, obj))

    def get_proxy_object(self, bus_name, path, introspection):
        assert bus_name == "org.bluez"
        assert path == "/org/bluez"
        assert "AgentManager1" in introspection
        return FakeProxy(self.calls)


def test_register_agent_registers_default_on_bluez():
    bus = FakeBus()
    asyncio.run(agent_mod.register_agent(bus))
    assert bus.exported[0][0] == agent_mod.AGENT_PATH
    assert isinstance(bus.exported[0][1], agent_mod.BtuiAgent)
    assert bus.calls == [
        ("register", agent_mod.AGENT_PATH, agent_mod.AGENT_CAPABILITY),
        ("default", agent_mod.AGENT_PATH),
    ]
    assert agent_mod.AGENT_CAPABILITY == "NoInputNoOutput"


def test_agent_exposes_bluez_agent_methods():
    iface = agent_mod.BtuiAgent()
    for name in (
        "Release",
        "RequestPinCode",
        "RequestPasskey",
        "RequestConfirmation",
        "RequestAuthorization",
        "AuthorizeService",
        "Cancel",
    ):
        assert hasattr(iface, name)
