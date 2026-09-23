import json
from mcp import Client
from app.tools.registry import registry

async def import_mcp_server(url: str, prefix: str = "mcp"):
    async with Client(url) as client:
        remote = await client.list_tools()
        for tool in remote.tools:
            remote_name = tool.name
            local_name = f"{prefix}_{remote_name}"
            async def call_remote(_remote_name=remote_name, **kwargs):
                async with Client(url) as c:
                    result = await c.call_tool(_remote_name, kwargs)
                    if getattr(result, "structured_content", None) is not None:
                        return json.dumps(result.structured_content, ensure_ascii=False)
                    return str(result.content)
            registry.register(local_name,tool.description or f"MCP tool {remote_name}",tool.inputSchema or {"type":"object","properties":{}},call_remote)
        return [f"{prefix}_{t.name}" for t in remote.tools]
