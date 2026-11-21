import os
import re
import tomllib
from dataclasses import MISSING, dataclass, fields
from pathlib import Path

_bots_home = os.environ.get("BOTS_HOME", "").strip()
BOT_ROOT = Path(_bots_home).expanduser() if _bots_home else Path.home() / ".bots"
COMMON_CONFIG_PATH = BOT_ROOT / "config.toml"
WORKSPACE_DIR = BOT_ROOT / "workspace"
AGENTS_DIR = BOT_ROOT / "agents"
PROFILES_DIR = BOT_ROOT / "profiles"
PROFILE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def load_profile() -> str | None:
    profile = os.environ.get("BOT_PROFILE", "").strip()
    if not profile:
        return None
    if not PROFILE_PATTERN.fullmatch(profile):
        raise ValueError(
            f"Invalid BOT_PROFILE {profile!r}: use letters, digits, '-' and '_', starting with a letter or digit."
        )
    return profile


def bot_dir(profile: str | None) -> Path | None:
    return PROFILES_DIR / profile if profile is not None else None


@dataclass(frozen=True)
class AgentConfig:
    model: str
    context_window: int
    base_url: str
    api_key_env_var: str
    input_modalities: list[str] | None = None


@dataclass(frozen=True)
class McpConfig:
    url: str
    auth_header_env_vars: dict[str, str] | None = None
    model_access: str | None = None
    disabled_tools: list[str] | None = None
    startup_timeout_seconds: float | None = None
    tool_timeout_seconds: float | None = None
    namespace: str | None = None
    id: str | None = None
    name: str | None = None


def _load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _check_top_level(data: dict, source: Path) -> dict:
    extra = sorted(set(data) - {"agent", "mcp"})
    if extra:
        raise ValueError(
            f"{source}: unexpected tables: {', '.join(extra)}; "
            "only [agent] and [mcp.<name>] tables are allowed"
        )
    return data


def _load_profile_config(profile_dir: Path | None) -> dict:
    if profile_dir is None:
        return {}
    path = profile_dir / "config.toml"
    try:
        return _check_top_level(_load_toml(path), path)
    except FileNotFoundError:
        return {}


def _load_common_config() -> dict:
    try:
        return _check_top_level(_load_toml(COMMON_CONFIG_PATH), COMMON_CONFIG_PATH)
    except FileNotFoundError:
        return {}


def _load_agent_raw(data: dict, source: Path) -> dict | None:
    raw = data.get("agent")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: [agent] must be a table")
    known = {field.name for field in fields(AgentConfig)}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ValueError(f"{source}: [agent] has unknown keys: {', '.join(unknown)}")
    return raw


def _load_agent_config(common: dict | None, profile: dict | None, profile_dir: Path | None) -> AgentConfig:
    if profile is not None:
        raw, source = profile, profile_dir / "config.toml"
    elif common is not None:
        raw, source = common, COMMON_CONFIG_PATH
    else:
        if profile_dir is not None:
            raise ValueError(
                f"No [agent] table in {COMMON_CONFIG_PATH} or {profile_dir / 'config.toml'}: "
                "configure the model endpoint in one of them"
            )
        raise ValueError(
            f"No profile selected and {COMMON_CONFIG_PATH} has no [agent] table: "
            "configure the model endpoint in the common config or select a profile"
        )
    missing = [
        field.name
        for field in fields(AgentConfig)
        if field.default is MISSING and field.name not in raw
    ]
    if missing:
        raise ValueError(f"{source}: [agent] is missing required keys: {', '.join(missing)}")
    return AgentConfig(**raw)


def _load_mcp_configs(data: dict, source: Path) -> dict[str, McpConfig]:
    known = {field.name for field in fields(McpConfig)}
    servers: dict[str, McpConfig] = {}
    raw_servers = data.get("mcp", {})
    if not isinstance(raw_servers, dict):
        raise ValueError(f"{source}: [mcp] must be a table")
    for name, raw in raw_servers.items():
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: [mcp.{name}] must be a table")
        unknown = sorted(set(raw) - known)
        if unknown:
            raise ValueError(f"{source}: [mcp.{name}] has unknown keys: {', '.join(unknown)}")
        if "url" not in raw:
            raise ValueError(f"{source}: [mcp.{name}] is missing the required 'url' key")
        servers[name] = McpConfig(**raw)
    return servers


def load_config(profile: str | None = None) -> AgentConfig:
    profile_dir = bot_dir(profile)
    common = _load_common_config()
    data = _load_profile_config(profile_dir)
    profile_path = profile_dir / "config.toml" if profile_dir is not None else None
    return _load_agent_config(
        _load_agent_raw(common, COMMON_CONFIG_PATH),
        _load_agent_raw(data, profile_path) if profile_path is not None else None,
        profile_dir,
    )


def load_mcp_servers(profile: str | None = None) -> dict[str, McpConfig]:
    profile_dir = bot_dir(profile)
    common = _load_common_config()
    data = _load_profile_config(profile_dir)
    profile_path = profile_dir / "config.toml" if profile_dir is not None else None
    return {
        "chrome": McpConfig(url="http://127.0.0.1:8080/mcp"),
        **_load_mcp_configs(common, COMMON_CONFIG_PATH),
        **(_load_mcp_configs(data, profile_path) if profile_path is not None else {}),
    }
