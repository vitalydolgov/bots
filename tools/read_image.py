import stat
from pathlib import Path

from google.genai import types

from config import WORKSPACE_DIR

MAX_IMAGE_BYTES = 5 * 1024 * 1024
TEMP_ROOT = Path("/tmp")

_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _sniff_media_type(data: bytes) -> str | None:
    for signature, media_type in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return media_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _resolve_path(requested: str) -> Path:
    if not requested.strip():
        raise ValueError("Path cannot be empty.")
    workspace = WORKSPACE_DIR.resolve()
    supplied = Path(requested)
    candidate = supplied if supplied.is_absolute() else workspace / supplied
    resolved = candidate.resolve()
    roots = [workspace]
    try:
        temp_root = TEMP_ROOT.resolve(strict=True)
    except OSError:
        temp_root = None
    if temp_root is not None:
        roots.append(temp_root)
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise ValueError(f"Path is outside the workspace: {requested}")
    return resolved


def read_image(path: str) -> dict:
    """Read an image file and view it. Supports PNG, JPEG, WebP and GIF files up to 5 MB. Relative paths resolve against the workspace.

    Args:
        path: Path to the image file, relative to the workspace or absolute.
    """
    try:
        resolved = _resolve_path(path)
    except ValueError as error:
        return {"error": str(error)}
    try:
        status = resolved.stat()
    except FileNotFoundError:
        return {"error": f"File not found: {path}"}
    except OSError as error:
        return {"error": f"Could not read {path}: {error}"}
    if not stat.S_ISREG(status.st_mode):
        return {"error": f"Path is not a regular file: {path}"}
    if status.st_size > MAX_IMAGE_BYTES:
        return {"error": f"Image is too large: {status.st_size} bytes (the limit is {MAX_IMAGE_BYTES} bytes)."}
    try:
        data = resolved.read_bytes()
    except OSError as error:
        return {"error": f"Could not read {path}: {error}"}
    media_type = _sniff_media_type(data)
    if media_type is None:
        return {"error": f"Not a supported image file (PNG, JPEG, WebP or GIF): {path}"}
    return {
        "text": f"Image file: {resolved.name} ({media_type}, {status.st_size} bytes)",
        "image": types.Part.from_bytes(data=data, mime_type=media_type),
    }


READ_IMAGE_TOOLS = [read_image]
