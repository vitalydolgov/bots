import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .model import ChatModel

WEB_DIR = Path(__file__).parent / "web"
WEB_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def make_handler(model: ChatModel):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_json(self, obj, status=200):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length))

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in WEB_FILES:
                name, content_type = WEB_FILES[parsed.path]
                body = (WEB_DIR / name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/session":
                self.send_json(model.session_info())
            elif parsed.path == "/api/events":
                after = int(parse_qs(parsed.query).get("after", ["0"])[0])
                self.send_json(model.events(after))
            else:
                self.send_json({"error": "not found"}, 404)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/message":
                data = self.read_json()
                text = (data.get("text") or "").strip()
                if not text:
                    self.send_json({"error": "empty message"}, 400)
                    return
                model.send_message(text)
                self.send_json({"ok": True})
            elif parsed.path == "/api/cancel":
                model.cancel()
                self.send_json({"ok": True})
            else:
                self.send_json({"error": "not found"}, 404)

    return Handler


def start_server(model: ChatModel, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(model))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
