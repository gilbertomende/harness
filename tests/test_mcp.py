import asyncio, time
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from app.config import settings
from app.mcp_client import client as mcp
from app.mcp_client.client import import_mcp_server, check_mcp_url, MCPPolicyError
from app.tools.registry import registry, Effect

server = MCPServer("test")
@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def echo(x: str) -> str: return x
@server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False))
def upsert(x: str) -> str: return "saved " + x
@server.tool()
def write_thing(x: str) -> str: return "wrote " + x
@server.tool()
def boom() -> str: raise RuntimeError("nope")
@server.tool()
def big() -> str: return "x" * 200_000
@server.tool()
async def slow() -> str:
    import anyio; await anyio.sleep(5); return "late"

def load(**kw): return asyncio.run(import_mcp_server(server, "t", source="mcp:test", **kw))

def test_import_registers_tools_with_schema():
    names = load()
    assert {"t_echo", "t_upsert", "t_write_thing", "t_boom"} <= set(names)
    spec = {s["function"]["name"]: s["function"] for s in registry.specs("admin")}
    assert spec["t_echo"]["parameters"]["required"] == ["x"]

def test_server_hints_never_grant_auto_execution():
    load()
    assert registry.effect("t_echo") is Effect.WRITE          # readOnlyHint alone is not trusted
    assert registry.effect("t_upsert") is Effect.WRITE
    assert registry.effect("t_write_thing") is Effect.DESTRUCTIVE  # MCP default destructiveHint=true
    assert "t_write_thing" not in {s["function"]["name"] for s in registry.specs("user")}  # elevated role

def test_admin_classification_is_the_only_way_to_query():
    load(read_only_tools=["echo"])
    assert registry.effect("t_echo") is Effect.QUERY
    assert "hi" in asyncio.run(registry.execute("t_echo", {"x": "hi"}))

def test_unclassified_tools_are_approval_gated():
    load()
    assert asyncio.run(registry.execute("t_upsert", {"x": "a"}, role="admin")) == "APPROVAL_REQUIRED"

def test_error_flag_and_output_limit(monkeypatch):
    load()
    assert asyncio.run(registry.execute("t_boom", {}, role="admin", approved=True)).startswith("ERROR:")
    monkeypatch.setattr(settings, "tool_output_max_chars", 1000)
    assert len(asyncio.run(registry.execute("t_big", {}, role="admin", approved=True))) <= 1000

def test_timeout(monkeypatch):
    load(); monkeypatch.setattr(settings, "mcp_timeout_seconds", 0.5)
    t = time.monotonic()
    with pytest.raises(TimeoutError): asyncio.run(registry.execute("t_slow", {}, role="admin", approved=True))
    assert time.monotonic() - t < 3

def test_unregister_source_removes_tools():
    load(); removed = registry.unregister_source("mcp:test")
    assert "t_echo" in removed
    with pytest.raises(ValueError): registry.get("t_echo", "admin")

@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x/mcp", "http:///nohost"])
def test_url_policy_rejects_bad_transport(url):
    with pytest.raises(MCPPolicyError): check_mcp_url(url)

def test_url_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "mcp_allowed_hosts", "mcp-demo, tools.internal")
    check_mcp_url("http://mcp-demo:9100/mcp")
    with pytest.raises(MCPPolicyError): check_mcp_url("http://evil.example/mcp")
