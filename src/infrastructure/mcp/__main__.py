"""Entry point for running MCP server.

Usage:
    # Local (stdio) - for local MCP clients
    python -m src.infrastructure.mcp

    # Network (SSE) - for remote Cherry Studio access
    python -m src.infrastructure.mcp --sse --port 8080 --host 0.0.0.0
"""

from .server import run_server

if __name__ == "__main__":
    run_server()
