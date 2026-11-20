import os
import sys

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from config import load_mcp_servers

DEFAULT_STARTUP_TIMEOUT_SECONDS = 30.0


def _headers(server) -> dict[str, str]:
    headers = {}
    for header, env_var in (server.auth_header_env_vars or {}).items():
        value = os.environ.get(env_var, "").strip()
        if value:
            headers[header] = value
        else:
            print(f"warning: MCP server {server.url}: environment variable {env_var} is not set; the {header} header will be missing", file=sys.stderr)
    return headers


def _tool_filter(server):
    if not server.disabled_tools:
        return None
    disabled = set(server.disabled_tools)

    def predicate(tool, readonly_context=None) -> bool:
        return tool.name not in disabled

    return predicate


def load_mcps(profile: str | None = None) -> list[McpToolset]:
    toolsets = []
    for name, server in load_mcp_servers(profile).items():
        for field in ("model_access", "tool_timeout_seconds", "id", "name"):
            if getattr(server, field) is not None:
                print(f"warning: MCP server {name}: '{field}' has no ADK equivalent and will be ignored", file=sys.stderr)
        toolsets.append(
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=server.url,
                    headers=_headers(server) or None,
                    timeout=server.startup_timeout_seconds or DEFAULT_STARTUP_TIMEOUT_SECONDS,
                ),
                tool_filter=_tool_filter(server),
                tool_name_prefix=server.namespace or name,
            )
        )
    return toolsets
