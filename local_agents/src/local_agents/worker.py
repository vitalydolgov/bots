import asyncio
import contextlib
import json
import os
import sqlite3
import sys
from pathlib import Path

from .model import ChatModel, SessionLoadError
from .store import (
    BOT_DIR,
    DB_PATH,
    JOURNAL_DIR,
    append_event,
    claim_command,
    connect,
    finish_command,
    register_agent,
    set_session_status,
)
from .web import start_server

POLL_SECONDS = 0.5


def _purge_project_modules(project: Path) -> None:
    root = str(project.resolve()) + os.sep
    own = str(Path(__file__).resolve().parent) + os.sep
    for name, module in list(sys.modules.items()):
        file = getattr(module, "__file__", None)
        if file is None:
            continue
        resolved = str(Path(file).resolve())
        if not resolved.startswith(root) or resolved.startswith(own):
            continue
        if "site-packages" in resolved or "dist-packages" in resolved:
            continue
        del sys.modules[name]


def _load_profile(project: Path, profile: str | None) -> object:
    if profile is None:
        os.environ.pop("BOT_PROFILE", None)
    else:
        os.environ["BOT_PROFILE"] = profile
    _purge_project_modules(project)
    from mistralai.vibe_agents.sdk.app import loader

    return loader.load_app(project)


class StoreOutput:
    def __init__(self, conn: sqlite3.Connection, session_id: str) -> None:
        self._conn = conn
        self._session_id = session_id

    def _emit(self, kind: str, payload: str) -> None:
        append_event(self._conn, self._session_id, kind, payload)

    def reply(self, text: str) -> None:
        self._emit("reply", text)

    def reply_done(self) -> None:
        self._emit("reply_done", "")

    def tool_call(self, name: str, arguments: object) -> None:
        self._emit("tool_call", json.dumps({"name": name, "arguments": arguments}))

    def tool_result(self, name: str, error: str | None) -> None:
        self._emit("tool_result", json.dumps({"name": name, "error": error}))

    def ask_approval(self, callback: object) -> object:
        from mistralai.vibe_agents.sdk.app.chat import ApprovalAnswer

        name = getattr(callback, "name", None) or getattr(callback, "tool_id", None) or "approval"
        self._emit("approval_denied", str(name))
        return ApprovalAnswer.DENY

    def notice(self, message: str) -> None:
        self._emit("notice", message)

    def turn_failed(self, message: str) -> None:
        self._emit("turn_failed", message)

    def turn_cancelled(self, reason: str | None) -> None:
        self._emit("turn_cancelled", reason or "")


async def _ensure_client(
    conn: sqlite3.Connection,
    loaded: object,
    sessions: dict[str, object],
    session_id: str,
) -> object:
    client = sessions.get(session_id)
    if client is not None:
        return client
    row = conn.execute("SELECT sdk_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    sdk_id = row["sdk_id"] if row else None
    if not sdk_id:
        raise RuntimeError("this session predates resume support; start a new one with --new")
    from mistralai.vibe_agents.sdk.transport import local as local_transport

    runtime = local_transport._running_process_runtime()
    if runtime is None:
        raise RuntimeError("the local runtime is not running")
    client = await runtime.get_session(
        sdk_id,
        reassemble=lambda: loaded.agent._reassemble_local_root(runtime, sdk_id),
    )
    sessions[session_id] = client
    return client


async def _detach_session(
    conn: sqlite3.Connection,
    sessions: dict[str, object],
    session_id: str,
) -> None:
    client = sessions.pop(session_id, None)
    if client is not None:
        await client.close()
    set_session_status(conn, session_id, "idle")
    append_event(conn, session_id, "session_detached", "")


async def handle_command(
    conn: sqlite3.Connection,
    loaded: object,
    sessions: dict[str, object],
    command: sqlite3.Row,
) -> None:
    from mistralai.vibe_agents.sdk.app import chat

    session_id = command["session_id"]
    payload = json.loads(command["payload"])
    try:
        if command["kind"] == "start":
            client = await loaded.agent._create_session()
            sessions[session_id] = client
            conn.execute(
                "UPDATE sessions SET sdk_id = ?, status = 'ready' WHERE id = ?",
                (client.session_id, session_id),
            )
            append_event(conn, session_id, "session_ready", client.session_id)
        elif command["kind"] == "resume":
            client = await _ensure_client(conn, loaded, sessions, session_id)
            set_session_status(conn, session_id, "ready")
            append_event(conn, session_id, "session_ready", client.session_id)
        elif command["kind"] == "message":
            try:
                client = await _ensure_client(conn, loaded, sessions, session_id)
                output = StoreOutput(conn, session_id)
                completed = await chat.run_turn(client, payload["text"], output)
            except asyncio.CancelledError:
                append_event(conn, session_id, "turn_cancelled", "")
                append_event(conn, session_id, "turn_done", "cancelled")
                finish_command(conn, command["id"], "done")
                raise
            append_event(conn, session_id, "turn_done", "completed" if completed else "failed")
        elif command["kind"] == "detach":
            await _detach_session(conn, sessions, session_id)
        else:
            raise RuntimeError(f"unknown command kind {command['kind']!r}")
        finish_command(conn, command["id"], "done")
    except Exception as exc:
        append_event(conn, session_id, "error", str(exc))
        finish_command(conn, command["id"], "failed")


async def serve(project: Path, profile: str | None, port: int, resume_ref: str | None) -> None:
    from mistralai import agents
    from mistralai.agents import experimental

    selected = profile
    if selected is None and not (BOT_DIR / "config.toml").is_file():
        raise SystemExit(f"No common config at {BOT_DIR / 'config.toml'}: add one or pass --profile <name>.")

    original_profile = os.environ.get("BOT_PROFILE")
    conn = connect()
    try:
        try:
            loaded = _load_profile(project, selected)
        except Exception as exc:
            raise SystemExit(f"Could not load {selected or 'bot'}: {exc}")
        agent_name = loaded.name
        register_agent(conn, agent_name, project.resolve())
        print(f"Serving {agent_name} from {project.resolve()}", flush=True)
    finally:
        if original_profile is None:
            os.environ.pop("BOT_PROFILE", None)
        else:
            os.environ["BOT_PROFILE"] = original_profile

    try:
        model = ChatModel.load(agent_name, resume_ref=resume_ref)
    except SessionLoadError as exc:
        raise SystemExit(str(exc))

    try:
        server = start_server(model, port)
    except OSError as exc:
        raise SystemExit(f"Could not listen on port {port}: {exc}")
    shown = model.session_info()["sdk_id"] or model.current_session_id()
    if model.resumed:
        print(f"Resuming session {shown}.", flush=True)
    else:
        print(f"Started session {shown}.", flush=True)
    print(f"Serving the web client at http://127.0.0.1:{port}/ — Ctrl+C to stop.", flush=True)

    agent_names = [agent_name]
    sessions: dict[str, object] = {}
    turn_task: asyncio.Task | None = None
    turn_session_id: str | None = None
    print(f"Polling {DB_PATH} for commands. Ctrl+C to stop.", flush=True)
    try:
        async with agents.local_runtime(
            journal_factory=experimental.JsonFileSessionJournal.in_directory(JOURNAL_DIR)
        ):
            try:
                while True:
                    if turn_task is not None and turn_task.done():
                        if not turn_task.cancelled() and (exc := turn_task.exception()) is not None:
                            print(f"Turn failed: {exc}", flush=True)
                        turn_task = None
                        turn_session_id = None
                    busy = turn_task is not None
                    if busy:
                        command = claim_command(conn, agent_names, only_kinds=["cancel"])
                        if command is None:
                            command = claim_command(conn, agent_names, only_kinds=["message"], session_id=turn_session_id)
                    else:
                        command = claim_command(conn, agent_names)
                    if command is None:
                        await asyncio.sleep(POLL_SECONDS)
                        continue
                    if command["kind"] == "cancel":
                        if busy and command["session_id"] == turn_session_id:
                            turn_task.cancel()
                            try:
                                await turn_task
                            except asyncio.CancelledError:
                                pass
                            turn_task = None
                            turn_session_id = None
                        else:
                            append_event(conn, command["session_id"], "notice", "No turn is running.")
                        finish_command(conn, command["id"], "done")
                        continue
                    if command["kind"] == "message":
                        if busy and command["session_id"] == turn_session_id:
                            payload = json.loads(command["payload"])
                            client = sessions.get(turn_session_id)
                            if client is None:
                                append_event(conn, command["session_id"], "error", "the running turn's session is not attached")
                                finish_command(conn, command["id"], "failed")
                                continue
                            from mistralai.vibe.harness.app_server import session as harness_session

                            try:
                                response = await client.send_message(
                                    [harness_session.TextContentBlock(text=payload["text"])]
                                )
                            except Exception as exc:
                                append_event(conn, command["session_id"], "error", str(exc))
                                finish_command(conn, command["id"], "failed")
                                continue
                            if response.steered is not True:
                                append_event(
                                    conn,
                                    command["session_id"],
                                    "notice",
                                    "The turn had already ended; your message started a new turn whose reply will not appear here.",
                                )
                            finish_command(conn, command["id"], "done")
                            continue
                        turn_session_id = command["session_id"]
                        turn_task = asyncio.create_task(handle_command(conn, loaded, sessions, command))
                        continue
                    await handle_command(conn, loaded, sessions, command)
            finally:
                if turn_task is not None and not turn_task.done():
                    turn_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await turn_task
                await _detach_session(conn, sessions, model.current_session_id())
    finally:
        server.shutdown()
        server.server_close()
