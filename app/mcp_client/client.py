"""MCP servers as tool providers (ADR-004). Server metadata is untrusted (SECURITY.md §8):
only the administrator can classify a remote tool as read-only; self-declared hints can only
make a tool more restrictive."""
import asyncio, json
from urllib.parse import urlparse
from mcp import Client
from app.config import settings
from app.tools.registry import registry, Effect

class MCPPolicyError(ValueError):
    pass

def check_mcp_url(url: str):
    """Transport/host policy for a registered MCP server URL."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise MCPPolicyError("MCP URL must be http(s)://host[:port]/path")
    allowed = settings.mcp_allowed_host_set
    if allowed and u.hostname.lower() not in allowed:
        raise MCPPolicyError(f"MCP host {u.hostname} is not in MCP_ALLOWED_HOSTS")

def classify(tool, read_only_tools) -> Effect:
    if tool.name in read_only_tools: return Effect.QUERY          # admin decision
    ann = tool.annotations
    if ann and (ann.read_only_hint or ann.destructive_hint is False): return Effect.WRITE
    return Effect.DESTRUCTIVE  # MCP default: destructiveHint=true when not read-only

def _format_result(result) -> str:
    if getattr(result, "structured_content", None) is not None:
        text = json.dumps(result.structured_content, ensure_ascii=False)
    else:
        text = "\n".join(getattr(c, "text", None) or c.model_dump_json() for c in result.content)
    text = text[:settings.tool_output_max_chars]
    return f"ERROR: {text}" if getattr(result, "is_error", False) else text

def _make_caller(target, remote_name: str):
    async def call_remote(**kwargs):
        async def run():
            async with Client(target) as c:
                return _format_result(await c.call_tool(remote_name, kwargs))
        try: return await asyncio.wait_for(run(), timeout=settings.mcp_timeout_seconds)
        except asyncio.TimeoutError: raise TimeoutError(f"MCP tool {remote_name} exceeded {settings.mcp_timeout_seconds}s")
    return call_remote

async def import_mcp_server(target, prefix: str = "mcp", read_only_tools=(), source: str | None = None):
    """Register the tools of an MCP server. `target` is a URL (or any transport accepted by mcp.Client)."""
    if isinstance(target, str): check_mcp_url(target)
    source = source or f"mcp:{prefix}"
    async def discover():
        async with Client(target) as client:
            return await client.list_tools()
    remote = await asyncio.wait_for(discover(), timeout=settings.mcp_timeout_seconds)
    registry.unregister_source(source)
    names = []
    for tool in remote.tools:
        local_name = f"{prefix}_{tool.name}"
        registry.register(local_name, tool.description or f"MCP tool {tool.name}",
                          tool.input_schema or {"type":"object","properties":{}},
                          _make_caller(target, tool.name), effect=classify(tool, set(read_only_tools)), source=source)
        names.append(local_name)
    return names
