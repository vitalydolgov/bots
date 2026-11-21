import os
import sys

from config import AGENTS_DIR, BOT_ROOT
from sync_agents import sync_agents

ADK_MAIN = "from google.adk.cli import main; main()"


def _has_session_service_uri(args: list[str]) -> bool:
    return any(arg == "--session_service_uri" or arg.startswith("--session_service_uri=") for arg in args)


def main() -> None:
    sync_agents()
    args = sys.argv[1:]
    command = [sys.executable, "-c", ADK_MAIN, "web", str(AGENTS_DIR)]
    if not _has_session_service_uri(args):
        command += ["--session_service_uri", f"sqlite:///{BOT_ROOT}/adk_sessions.db"]
    command += args
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
