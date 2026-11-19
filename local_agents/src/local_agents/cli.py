"""Local stand-in for the hosted control plane: a SQLite store the worker polls.

`agents serve` registers the agent with the hosted control plane and polls its
task queue; sessions and their events live on the service. This package is the
same shape without the service: a SQLite file holds the agent registry, the
sessions, the command queue and the event log, and the worker polls it.
Sessions are journaled to disk, so a later `serve --resume` reattaches to one.

    uv run local-agents serve                  # serve the common config and its web client at http://127.0.0.1:8000/
    uv run local-agents serve --profile grad   # serve the grad profile instead
    uv run local-agents serve --resume <id>    # resume a specific session
"""

import os

os.environ.setdefault("AGENTS_SDK_EXPERIMENTAL_WARNINGS", "0")

import argparse
import asyncio
from pathlib import Path

from .worker import serve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve", help="Serve one agent and its web client.")
    serve_parser.add_argument("--path", type=Path, default=Path("."))
    serve_parser.add_argument("--profile", default=None, help="Serve this profile instead of the common config.")
    serve_parser.add_argument("--port", type=int, default=8000)
    session = serve_parser.add_mutually_exclusive_group()
    session.add_argument("--new", action="store_true", help="Start a fresh session (the default).")
    session.add_argument("--resume", default=None, help="Resume a specific session by id.")

    args = parser.parse_args()
    if args.command == "serve":
        try:
            asyncio.run(serve(args.path, args.profile, args.port, args.resume))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
