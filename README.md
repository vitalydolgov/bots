# Bots

A framework for creating specialized bots built on Google ADK. It provides a shared foundation for defining, configuring, and running purpose-built agents, so each bot can focus on its own domain and behavior. Each bot runs as a profile with its own configuration and memory, layered on top of a common setup shared by all profiles.

## Features

- Persistent memory — the agent remembers things across turns and sessions.
- Skills — the agent can use skills and author its own, so it can learn new procedures over time.
- MCP — the agent can call tools on remote MCP servers.
- Chrome — the agent can drive a headless desktop Chrome browser through Chrome DevTools.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — installs the dependencies and runs the bot.
- Python 3.12+ on the login-shell PATH. Check with `bash -lc 'python3 --version'`; if it reports an older version, prepend a newer Python to PATH in `~/.bash_profile`.
- [Chrome](https://www.google.com/chrome/) — required for the chrome skill.
- [Node.js](https://nodejs.org/) — provides `npx`, required for the chrome skill's MCP bridge.

## Setup

From the project root:

```sh
uv sync
```

This creates a virtual environment in `.venv` and installs the project dependencies.

## Profiles

Each bot can run as a profile with its own configuration and memory, stored under `~/.bots/profiles/<profile>/`. The workspace and skills are shared by all profiles and stored under `~/.bots/workspace/`. With no profile selected, the bot runs with no profile:

- It reads only the common config, `~/.bots/config.toml`.
- It uses a shared memory file at `~/.bots/MEMORY.md`.
- It uses a shared identity file at `~/.bots/IDENTITY.md`.
- It registers under the agent name `bot`.

A profile directory holds `config.toml`, `MEMORY.md` and `IDENTITY.md`. `IDENTITY.md`, when present, is injected into the agent's identity section; create it to define the bot's identity. The agent's name is the profile name. To create a profile, make `~/.bots/profiles/<name>/` with a `config.toml`; the rest is created on first use. The shared workspace lives in `~/.bots/workspace/`; skills live in `~/.bots/workspace/.agents/skills/`, seeded from the built-in skills on first use.

### Running all profiles in one UI

Generate one shim per profile and serve them together:

```sh
python3 scripts/sync-agents.py
uv run adk web ~/.bots/agents --session_service_uri sqlite:///$HOME/.bots/adk_sessions.db
```

The UI lists `bot` (the default profile) and one agent per profile, and you can switch between them without restarting. Sessions are isolated per agent — the app name is the agent name — so all profiles can share one database. Re-run the generator after adding or removing a profile; stale shims it generated are removed automatically.

- Profile names may only contain letters, digits and underscores to appear as agents; a profile with other characters can still be run with `BOT_PROFILE` (see below).
- In this mode the project `.env` is not loaded; keep secrets in the environment or in `~/.bots/.env` (it is found by walking up from `~/.bots/agents/`).

### Running a single profile

```sh
BOT_PROFILE=anotherbot uv run adk web . --session_service_uri sqlite:///$HOME/.bots/adk_sessions_anotherbot.db
```

`BOT_PROFILE` may also be set in `.env`. In this mode all profiles share the app name `bot` (the project directory name), so point `--session_service_uri` at a different database per profile to keep sessions separate.

## Configuration

Configuration has two levels:

- Common — `~/.bots/config.toml`, common to all profiles. Holds the default model endpoint and MCP servers shared by every bot.
- Profile — `~/.bots/profiles/<profile>/config.toml`, where `<profile>` is the selected profile (via `BOT_PROFILE`, or the agent picked in the multi-agent UI). Holds the model endpoint (replacing the common one entirely) and any profile-specific MCP servers; a profile MCP server with the same name as a common one replaces it. Read only when a profile is selected; otherwise only the common config is read.

See [docs/config.md](docs/config.md) for the full format.

### Environment

Set these in the environment, in a `.env` file in the project root (single-agent mode), or in `~/.bots/.env` (multi-agent mode). Variables already set in the environment take precedence over `.env`; the file only fills in what is missing.

- The environment variable named by `api_key_env_var` in `[agent]` — authenticates with the model endpoint.
- Any variables referenced by `auth_header_env_vars` of the MCP servers in `~/.bots/config.toml` and, when a profile is selected, `~/.bots/profiles/<profile>/config.toml`.

## Run

The agent is served with `adk web`, the ADK development web UI. From the project root:

```sh
uv run adk web . --session_service_uri sqlite:///$HOME/.bots/adk_sessions.db
```

Then open the printed URL (default http://127.0.0.1:8000) and pick the `bot` agent. To serve every profile in one UI, see Profiles.

- Sessions persist in the SQLite database at the given URI and survive restarts. Without `--session_service_uri`, sessions are stored per agent in a `.adk` directory next to the project root; pass `--no_use_local_storage` to keep sessions in memory only.
- The agent executes commands directly on your machine; there is no sandbox.
