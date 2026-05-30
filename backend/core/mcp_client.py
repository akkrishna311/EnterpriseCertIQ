"""
MCP tool client — wraps both the own FastMCP server and the Microsoft Learn MCP server.

Uses the official `mcp` Python SDK with the Streamable-HTTP transport, which performs
the required `initialize` handshake + session negotiation. (A bare JSON-RPC POST does
not satisfy the Streamable-HTTP protocol that learn.microsoft.com/api/mcp expects.)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


def _content_to_payload(result: Any) -> Any:
    """Extract a usable payload from an MCP CallToolResult."""
    # Prefer structured content when the server provides it.
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured

    content = getattr(result, "content", None) or []
    texts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    if not texts:
        return {"error": "empty MCP response"}

    joined = "\n".join(texts)
    try:
        return json.loads(joined)
    except Exception:
        return joined


class MCPToolClient:
    """Async client for calling MCP tools over the Streamable-HTTP transport.

    `endpoint` is the full MCP URL (e.g. https://learn.microsoft.com/api/mcp
    or http://localhost:8001/mcp). A fresh session is opened per call — simple
    and robust for this workload; agents make only a handful of calls per run.
    """

    def __init__(self, endpoint: str, name: str):
        self.endpoint = endpoint
        self.name = name
        self._tools: Optional[list[dict]] = None

    async def list_tools(self) -> list[dict]:
        if self._tools is not None:
            return self._tools
        try:
            from datetime import timedelta

            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            async with streamablehttp_client(self.endpoint, timeout=timedelta(seconds=15)) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    self._tools = [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "inputSchema": t.inputSchema or {"type": "object", "properties": {}},
                        }
                        for t in listed.tools
                    ]
                    return self._tools
        except Exception as e:
            logger.warning("Could not list tools from %s: %s", self.name, e)
            return []

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        try:
            from datetime import timedelta

            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            async with streamablehttp_client(self.endpoint, timeout=timedelta(seconds=15)) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return _content_to_payload(result)
        except Exception as e:
            logger.error("MCP tool call failed [%s.%s]: %s", self.name, tool_name, e)
            return {"error": str(e)}

    def as_openai_tools(self, tool_schemas: list[dict]) -> list[dict]:
        """Convert MCP tool list to OpenAI tool-calling format."""
        result = []
        for t in tool_schemas:
            result.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                },
            })
        return result


def get_own_mcp_client() -> MCPToolClient:
    s = get_settings()
    return MCPToolClient(f"{s.own_mcp_url}/mcp", "enterprisecertiq-tools")


def get_learn_mcp_client() -> MCPToolClient:
    s = get_settings()
    return MCPToolClient(s.ms_learn_mcp_url, "ms-learn")
