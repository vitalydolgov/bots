import tempfile
import unittest
from pathlib import Path

from local_agents.model import ChatModel, SessionLoadError
from local_agents.store import connect, create_session, is_turn_running, register_agent


class ChatModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "local_serve.db"
        self.connect_fn = lambda: connect(self.db_path)
        conn = self.connect_fn()
        try:
            register_agent(conn, "bot", Path("."))
        finally:
            conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def make_started_session(self, sdk_id: str, created_at: float) -> str:
        conn = self.connect_fn()
        try:
            session_id = create_session(conn, "bot")
            conn.execute(
                "UPDATE sessions SET sdk_id = ?, created_at = ? WHERE id = ?",
                (sdk_id, created_at, session_id),
            )
            return session_id
        finally:
            conn.close()

    def commands(self) -> list[tuple[str, str]]:
        conn = self.connect_fn()
        try:
            rows = conn.execute("SELECT kind, session_id FROM commands ORDER BY id").fetchall()
            return [(row["kind"], row["session_id"]) for row in rows]
        finally:
            conn.close()

    def test_unknown_agent_fails(self):
        with self.assertRaises(SessionLoadError) as ctx:
            ChatModel.load("nope", connect_fn=self.connect_fn)
        self.assertIn("No agent named nope", str(ctx.exception))

    def test_resume_unknown_ref_fails(self):
        with self.assertRaises(SessionLoadError) as ctx:
            ChatModel.load("bot", resume_ref="missing", connect_fn=self.connect_fn)
        self.assertIn("No session missing", str(ctx.exception))

    def test_resume_by_id(self):
        session_id = self.make_started_session("sdk-1", 1000.0)
        model = ChatModel.load("bot", resume_ref=session_id, connect_fn=self.connect_fn)
        self.assertEqual(model.session_id, session_id)
        self.assertTrue(model.resumed)
        self.assertIn(("resume", session_id), self.commands())

    def test_resume_by_sdk_id(self):
        session_id = self.make_started_session("sdk-1", 1000.0)
        model = ChatModel.load("bot", resume_ref="sdk-1", connect_fn=self.connect_fn)
        self.assertEqual(model.session_id, session_id)
        self.assertTrue(model.resumed)
        self.assertIn(("resume", session_id), self.commands())

    def test_resume_ref_for_another_agent_fails(self):
        conn = self.connect_fn()
        try:
            register_agent(conn, "grad", Path("."))
            other = create_session(conn, "grad")
            conn.execute("UPDATE sessions SET sdk_id = ? WHERE id = ?", ("sdk-grad", other))
        finally:
            conn.close()
        for ref in (other, "sdk-grad"):
            with self.assertRaises(SessionLoadError) as ctx:
                ChatModel.load("bot", resume_ref=ref, connect_fn=self.connect_fn)
            self.assertIn("grad", str(ctx.exception))

    def test_default_creates_fresh_session(self):
        started = self.make_started_session("sdk-1", 1000.0)
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        self.assertNotEqual(model.session_id, started)
        self.assertFalse(model.resumed)
        commands = self.commands()
        self.assertIn(("start", model.session_id), commands)
        self.assertNotIn(("resume", started), commands)

    def test_fresh_agent_creates_session(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        self.assertFalse(model.resumed)
        self.assertIn(("start", model.session_id), self.commands())

    def test_send_message_enqueues_message(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("hello")
        conn = self.connect_fn()
        try:
            row = conn.execute(
                "SELECT payload FROM commands WHERE session_id = ? AND kind = 'message'",
                (model.session_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["payload"], '{"text": "hello"}')

    def test_send_message_appends_user_message_event(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("hello")
        events = model.events(0)["events"]
        self.assertEqual([(e["kind"], e["payload"]) for e in events], [("user_message", "hello")])

    def test_send_message_enqueues_message_while_turn_running(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("first")
        model.send_message("second")
        conn = self.connect_fn()
        try:
            rows = conn.execute(
                "SELECT kind, payload FROM commands WHERE session_id = ? ORDER BY id",
                (model.session_id,),
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual([row["kind"] for row in rows], ["start", "message", "message"])
        self.assertEqual(rows[-1]["payload"], '{"text": "second"}')

    def test_send_message_enqueues_message_after_turn_done(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("first")
        conn = self.connect_fn()
        try:
            conn.execute("UPDATE commands SET status = 'done' WHERE kind = 'message'")
        finally:
            conn.close()
        model.send_message("second")
        self.assertEqual([kind for kind, _ in self.commands()], ["start", "message", "message"])

    def test_pending_message_counts_as_turn_running(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        model.send_message("first")
        conn = self.connect_fn()
        try:
            busy = is_turn_running(conn, model.session_id)
        finally:
            conn.close()
        self.assertTrue(busy)

    def test_events_reports_empty_log_and_idle(self):
        model = ChatModel.load("bot", connect_fn=self.connect_fn)
        self.assertEqual(model.events(0), {"busy": False, "events": []})


if __name__ == "__main__":
    unittest.main()
