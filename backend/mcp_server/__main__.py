"""Allows running: python3 -m backend.mcp_server.server"""
from backend.mcp_server.server import mcp
from config.settings import get_settings

s = get_settings()
mcp.run(transport="streamable-http", host="0.0.0.0", port=s.own_mcp_port)
