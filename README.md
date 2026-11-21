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

## The bots root

Everything the bot reads and writes lives under a single root directory, `~/.bots` by default. Set the `BOTS_HOME` environment variable to use a different root; every path below derives from it:

- `<BOTS_HOME>/config.toml` — the common config, shared by all profiles.
- `<BOTS_HOME>/profiles/<profile>/` — per-profile config, memory and identity.
- `<BOTS_HOME>/workspace/` — the shared workspace, including skills.
- `<BOTS_HOME>/agents/` — the generated agent shims served by `adk web`.
- `<BOTS_HOME>/adk_sessions.db` — the default session database.
- `<BOTS_HOME>/.env` — secrets for multi-agent mode.

## Installing the `bots` command

To run the bots from any directory, install the project as a uv tool:

```sh
uv tool install .
```

This puts a `bots` command on your PATH. `bots` syncs the agent shims under `<BOTS_HOME>/agents/` and then starts `adk web` against them, forwarding any extra arguments to `adk web` (for example, `bots --port 8123`). Sessions default to `sqlite:///<BOTS_HOME>/adk_sessions.db`; pass `--session_service_uri` to use a different database.

The tool venv is a snapshot of the project: after changing the code, reinstall with `uv tool install --reinstall .`.

## Profiles

Each bot can run as a profile with its own configuration and memory, stored under `<BOTS_HOME>/profiles/<profile>/`. The workspace and skills are shared by all profiles and stored under `<BOTS_HOME>/workspace/`. With no profile selected, the bot runs with no profile:

- It reads only the common config, `<BOTS_HOME>/config.toml`.
- It uses a shared memory file at `<BOTS_HOME>/MEMORY.md`.
- It uses a shared identity file at `<BOTS_HOME>/IDENTITY.md`.
- It registers under the agent name `bot`.

A profile directory holds `config.toml`, `MEMORY.md` and `IDENTITY.md`. `IDENTITY.md`, when present, is injected into the agent's identity section; create it to define the bot's identity. The agent's name is the profile name. To create a profile, make `<BOTS_HOME>/profiles/<name>/` with a `config.toml`; the rest is created on first use. The shared workspace lives in `<BOTS_HOME>/workspace/`; skills live in `<BOTS_HOME>/workspace/.agents/skills/`, seeded from the built-in skills on first use.

### Running all profiles in one UI

```sh
bots
```

This generates one shim per profile under `<BOTS_HOME>/agents/` and serves them together. The UI lists `bot` (the default profile) and one agent per profile, and you can switch between them without restarting. Sessions are isolated per agent — the app name is the agent name — so all profiles can share one database. The shims are synced every time `bots` starts, and stale shims it generated are removed automatically. To sync the shims without starting the server, run `python3 scripts/sync-agents.py`.

- Profile names may only contain letters, digits and underscores to appear as agents; a profile with other characters can still be run with `BOT_PROFILE` (see below).
- In this mode the project `.env` is not loaded; keep secrets in the environment or in `<BOTS_HOME>/.env` (it is found by walking up from `<BOTS_HOME>/agents/`).

### Running a single profile

```sh
BOT_PROFILE=anotherbot uv run adk web . --session_service_uri sqlite:///$HOME/.bots/adk_sessions_anotherbot.db
```

`BOT_PROFILE` may also be set in `.env`. In this mode all profiles share the app name `bot` (the project directory name), so point `--session_service_uri` at a different database per profile to keep sessions separate.

## Configuration

Configuration has two levels:

- Common — `<BOTS_HOME>/config.toml`, common to all profiles. Holds the default model endpoint and MCP servers shared by every bot.
- Profile — `<BOTS_HOME>/profiles/<profile>/config.toml`, where `<profile>` is the selected profile (via `BOT_PROFILE`, or the agent picked in the multi-agent UI). Holds the model endpoint (replacing the common one entirely) and any profile-specific MCP servers; a profile MCP server with the same name as a common one replaces it. Read only when a profile is selected; otherwise only the common config is read.

See [docs/config.md](docs/config.md) for the full format.

### Environment

Set these in the environment, in a `.env` file in the project root (single-agent mode), or in `<BOTS_HOME>/.env` (multi-agent mode). Variables already set in the environment take precedence over `.env`; the file only fills in what is missing.

- The environment variable named by `api_key_env_var` in `[agent]` — authenticates with the model endpoint.
- Any variables referenced by `auth_header_env_vars` of the MCP servers in `<BOTS_HOME>/config.toml` and, when a profile is selected, `<BOTS_HOME>/profiles/<profile>/config.toml`.

## Run

The agent is served with `adk web`, the ADK development web UI. With the `bots` command installed (see above), run:

```sh
bots
```

Then open the printed URL (default http://127.0.0.1:8000) and pick an agent. To serve a single profile from the project root instead:

```sh
uv run adk web . --session_service_uri sqlite:///$HOME/.bots/adk_sessions.db
```

- Sessions persist in the SQLite database at the given URI and survive restarts. Without `--session_service_uri`, sessions are stored per agent in a `.adk` directory next to the project root; pass `--no_use_local_storage` to keep sessions in memory only.
- The agent executes commands directly on your machine; there is no sandbox.
