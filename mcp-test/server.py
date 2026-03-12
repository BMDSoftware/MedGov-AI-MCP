from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http_manager import TransportSecuritySettings

mcp = FastMCP(
    "test-server",
    host="0.0.0.0",
    port=3001,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
def hello(name: str) -> str:
    """Say hello to someone"""
    return f"Hello {name}, I am a test MCP server!"


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers"""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
