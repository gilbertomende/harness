import asyncio
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from app.mcp_client.client import import_mcp_server
from app.tools.registry import registry

server = MCPServer("test")
@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def echo(x: str) -> str: return x
@server.tool()
def write_thing(x: str) -> str: return "wrote " + x
@server.tool()
def boom() -> str: raise RuntimeError("nope")

def test_import_registers_tools_with_schema_and_mutating_flag():
    names = asyncio.run(import_mcp_server(server, "t"))
    assert set(names) == {"t_echo", "t_write_thing", "t_boom"}
    spec = {s["function"]["name"]: s["function"] for s in registry.specs("user")}
    assert spec["t_echo"]["parameters"]["required"] == ["x"]
    assert not registry.is_mutating("t_echo")
    assert registry.is_mutating("t_write_thing")

def test_call_and_error_flag():
    asyncio.run(import_mcp_server(server, "t"))
    assert "hi" in asyncio.run(registry.execute("t_echo", {"x": "hi"}))
    assert asyncio.run(registry.execute("t_write_thing", {"x": "a"})) == "APPROVAL_REQUIRED"
    assert asyncio.run(registry.execute("t_boom", {}, approved=True)).startswith("ERROR:")
