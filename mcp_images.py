import base64
import binascii

from google.genai import types


def mcp_image_callback(tool, args, tool_context, tool_response):
    """Move image blocks in MCP tool results into function response parts.

    MCP servers return images as base64 blocks inside the result's content
    list. ADK only forwards media that is a types.Part, so without this the
    model receives the base64 payload as text.
    """
    if not isinstance(tool_response, dict):
        return None
    content = tool_response.get("content")
    if not isinstance(content, list):
        return None
    converted = []
    changed = False
    for block in content:
        if isinstance(block, dict) and block.get("type") == "image" and block.get("data"):
            mime_type = block.get("mimeType") or block.get("mime_type") or "image/png"
            try:
                data = base64.b64decode(block["data"])
            except (binascii.Error, ValueError):
                converted.append(block)
                continue
            converted.append(types.Part.from_bytes(data=data, mime_type=mime_type))
            changed = True
        else:
            converted.append(block)
    if not changed:
        return None
    return {**tool_response, "content": converted}
