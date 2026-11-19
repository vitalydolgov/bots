# Local agents

`local-agents` is an experimental local stand-in for `agents serve` and `agents chat`. The hosted commands register the agent with Mistral's control plane and poll its task queue; sessions and their events live on the service. `local-agents` keeps the same shape without the service: a local store holds the agent registry, the sessions, a command queue and an event log, and a worker polls it. Nothing is registered with Mistral and the Session API is not used, so only the model endpoint key from `~/.bots/config.toml` is needed.

## Commands

```sh
uv run local-agents serve                  # serve the common config and its web client at http://127.0.0.1:8000/
uv run local-agents serve --profile grad   # serve the grad profile instead
uv run local-agents serve --resume <id>    # resume a specific session
```

### `serve`

Loads exactly one profile and serves it together with a web client at `http://127.0.0.1:8000/`:

- The common config `~/.bots/config.toml`, served as `bot` (the default).
- `--profile <name>` serves the profile `~/.bots/profiles/<name>/config.toml` instead.

A profile that fails to load is a fatal error; nothing else is served. Stop it with Ctrl+C. The agent stays registered but receives no sessions until you serve it again.

| Flag | Description |
| --- | --- |
| `--path` | Project directory to load the agent from. Defaults to `.`. |
| `--profile` | Serve this profile instead of the common config. |
| `--port` | Port to listen on. Defaults to 8000. |
| `--new` | Start a fresh session (the default). |
| `--resume` | Resume a specific session, by either of its ids (see below). |

The page streams the event log into the browser and sends messages through the same command queue. While a turn is running, submitting a message injects it into the running turn instead of queueing it for after the turn; a "Stop" button interrupts the turn. Stopping the server with Ctrl+C detaches from the session; it stays resumable. By default `serve` starts a fresh session; pass `--resume <id>` to reattach to an earlier one.

## Architecture

Everything goes through the store; no component talks to another directly.

Components:

- Store — a SQLite database holding the agent registry, the sessions, a command queue and an event log. It is the only shared state.
- Worker — polls the command queue, claims one command at a time, and runs it in-process: `start` creates a session, `resume` reattaches to a journaled one, `message` runs a turn (or, while a turn is running for the session, injects the message into it), `cancel` interrupts the running turn, `detach` releases the session. Turns append events to the log as they run.
- Model — the web client's model layer. It owns session resolution (resume a specific session, or start a fresh one), enqueues the matching command, and holds the current session id behind a lock. It contains no HTTP code, so session loading can be exercised against a temporary store without starting the web server.
- Web client — a thin HTTP adapter over the model. It serves the page, exposes the session, events, message and cancel endpoints, and renders the event log in the browser.
- CLI — the entry point; wires the `serve` subcommand to the worker and the web client.

`serve` runs the worker and the web client in one process, bound to a single session chosen at startup.

A message sent while a turn is running is injected into the running turn, so the agent sees it mid-turn; the running turn can be interrupted, which leaves the session usable. If the turn ends before the message is delivered, the message runs as a new turn instead.

Sessions are journaled to disk, so they survive restarts and can be resumed in a later process.

Each session has two ids; `--resume` accepts either.

## State

All state lives under `~/.bots/`:

- `~/.bots/local_serve.db` — the store.
- `~/.bots/sessions/` — session journals.

Deleting both resets all local state.
