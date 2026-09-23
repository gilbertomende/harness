"""Small MCP server (streamable HTTP) used ONLY for local homologation (compose.e2e.yaml).

Exposes one read-only tool and one tool without a read-only annotation, so both the direct
path and the approval gate of the harness can be exercised against a real MCP transport.
"""
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

server = MCPServer("harness-e2e-demo")
NOTES: list[str] = []

@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

@server.tool()
def append_note(text: str) -> str:
    """Append a note (state-changing; the harness must require approval)."""
    NOTES.append(text)
    return f"notes={len(NOTES)} last={text}"

if __name__ == "__main__":
    server.run(transport="streamable-http", host="0.0.0.0", port=9100,
               transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
