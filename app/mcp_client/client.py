import json
from mcp import Client
from app.tools.registry import registry

def _format_result(result) -> str:
    if getattr(result, "structured_content", None) is not None:
        text = json.dumps(result.structured_content, ensure_ascii=False)
    else:
        text = "\n".join(getattr(c, "text", None) or c.model_dump_json() for c in result.content)
    return f"ERROR: {text}" if getattr(result, "is_error", False) else text

def _make_caller(target, remote_name: str):
    async def call_remote(**kwargs):
        async with Client(target) as c:
            return _format_result(await c.call_tool(remote_name, kwargs))
    return call_remote

async def import_mcp_server(target, prefix: str = "mcp"):
    """Register the tools of an MCP server. `target` is a URL (or any transport accepted by mcp.Client)."""
    async with Client(target) as client:
        remote = await client.list_tools()
    names = []
    for tool in remote.tools:
        local_name = f"{prefix}_{tool.name}"
        # Remote tools are mutating (approval-gated) unless the server declares them read-only.
        read_only = bool(tool.annotations and tool.annotations.read_only_hint)
        registry.register(local_name, tool.description or f"MCP tool {tool.name}",
                          tool.input_schema or {"type":"object","properties":{}},
                          _make_caller(target, tool.name), mutating=not read_only)
        names.append(local_name)
    return names
