import sqlite3
import threading
from collections.abc import Callable

from .store import (
    append_event,
    connect,
    create_session,
    enqueue,
    find_session,
    get_agent,
    is_turn_running,
    read_events,
    session_sdk_id,
)

ConnectFn = Callable[[], sqlite3.Connection]


class SessionLoadError(Exception):
    pass


class ChatModel:
    def __init__(self, agent: str, session_id: str, resumed: bool, connect_fn: ConnectFn = connect) -> None:
        self.agent = agent
        self.session_id = session_id
        self.resumed = resumed
        self.lock = threading.Lock()
        self._connect = connect_fn

    @classmethod
    def load(cls, agent_name: str, resume_ref: str | None = None, connect_fn: ConnectFn = connect) -> "ChatModel":
        conn = connect_fn()
        try:
            if get_agent(conn, agent_name) is None:
                raise SessionLoadError(f"No agent named {agent_name}. Start it with `uv run local-agents serve`.")
            resumed = False
            session_id = None
            if resume_ref is not None:
                row = find_session(conn, resume_ref)
                if row is None:
                    raise SessionLoadError(f"No session {resume_ref}.")
                if row["agent"] != agent_name:
                    raise SessionLoadError(f"Session {resume_ref} belongs to agent {row['agent']}, not {agent_name}.")
                session_id = row["id"]
                enqueue(conn, session_id, "resume", {})
                resumed = True
            if session_id is None:
                session_id = create_session(conn, agent_name)
        finally:
            conn.close()
        return cls(agent_name, session_id, resumed, connect_fn)

    def current_session_id(self) -> str:
        with self.lock:
            return self.session_id

    def session_info(self) -> dict:
        with self.lock:
            session_id = self.session_id
        conn = self._connect()
        try:
            sdk_id = session_sdk_id(conn, session_id)
        finally:
            conn.close()
        return {"agent": self.agent, "session_id": session_id, "sdk_id": sdk_id}

    def events(self, after: int) -> dict:
        with self.lock:
            session_id = self.session_id
        conn = self._connect()
        try:
            rows = read_events(conn, session_id, after)
            busy = is_turn_running(conn, session_id)
        finally:
            conn.close()
        return {
            "busy": busy,
            "events": [
                {"id": e["id"], "kind": e["kind"], "payload": e["payload"]}
                for e in rows
            ],
        }

    def send_message(self, text: str) -> None:
        with self.lock:
            session_id = self.session_id
        conn = self._connect()
        try:
            enqueue(conn, session_id, "message", {"text": text})
            append_event(conn, session_id, "user_message", text)
        finally:
            conn.close()

    def cancel(self) -> None:
        with self.lock:
            session_id = self.session_id
        conn = self._connect()
        try:
            enqueue(conn, session_id, "cancel", {})
        finally:
            conn.close()
