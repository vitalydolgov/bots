import json
import sqlite3
import time
import uuid
from pathlib import Path

BOT_DIR = Path.home() / ".bots"
DB_PATH = BOT_DIR / "local_serve.db"
JOURNAL_DIR = BOT_DIR / "sessions"

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents(
    name TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
    id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    sdk_id TEXT
);
CREATE TABLE IF NOT EXISTS commands(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
    if "sdk_id" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN sdk_id TEXT")
    return conn


def register_agent(conn: sqlite3.Connection, name: str, project: Path) -> None:
    conn.execute(
        "INSERT INTO agents(name, project, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET project=excluded.project",
        (name, str(project), time.time()),
    )


def get_agent(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()


def create_session(conn: sqlite3.Connection, agent: str) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions(id, agent, status, created_at) VALUES (?, ?, 'starting', ?)",
        (session_id, agent, time.time()),
    )
    enqueue(conn, session_id, "start", {})
    return session_id


def find_session(conn: sqlite3.Connection, ref: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM sessions WHERE id = ? OR sdk_id = ?", (ref, ref)
    ).fetchone()


def set_session_status(conn: sqlite3.Connection, session_id: str, status: str) -> None:
    conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))


def enqueue(conn: sqlite3.Connection, session_id: str, kind: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO commands(session_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
        (session_id, kind, json.dumps(payload), time.time()),
    )


def claim_command(conn: sqlite3.Connection, agents: list[str], only_kinds: list[str] | None = None, session_id: str | None = None) -> sqlite3.Row | None:
    if not agents:
        return None
    placeholders = ", ".join("?" for _ in agents)
    kind_clause = ""
    params: list = list(agents)
    if only_kinds:
        kind_placeholders = ", ".join("?" for _ in only_kinds)
        kind_clause = f" AND commands.kind IN ({kind_placeholders})"
        params.extend(only_kinds)
    session_clause = ""
    if session_id is not None:
        session_clause = " AND commands.session_id = ?"
        params.append(session_id)
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT commands.* FROM commands JOIN sessions ON sessions.id = commands.session_id "
        f"WHERE commands.status = 'pending' AND sessions.agent IN ({placeholders}){kind_clause}{session_clause} "
        "ORDER BY commands.id LIMIT 1",
        params,
    ).fetchone()
    if row is None:
        conn.execute("COMMIT")
        return None
    conn.execute("UPDATE commands SET status = 'running' WHERE id = ?", (row["id"],))
    conn.execute("COMMIT")
    return row


def finish_command(conn: sqlite3.Connection, command_id: int, status: str) -> None:
    conn.execute("UPDATE commands SET status = ? WHERE id = ?", (status, command_id))


def append_event(conn: sqlite3.Connection, session_id: str, kind: str, payload: str) -> None:
    conn.execute(
        "INSERT INTO events(session_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
        (session_id, kind, payload, time.time()),
    )


def session_sdk_id(conn: sqlite3.Connection, session_id: str) -> str | None:
    row = conn.execute("SELECT sdk_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return row["sdk_id"] if row else None


def is_turn_running(conn: sqlite3.Connection, session_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM commands WHERE session_id = ? AND kind = 'message' "
        "AND status IN ('pending', 'running') LIMIT 1",
        (session_id,),
    ).fetchone()
    return row is not None


def read_events(conn: sqlite3.Connection, session_id: str, after_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM events WHERE session_id = ? AND id > ? ORDER BY id",
        (session_id, after_id),
    ).fetchall()
