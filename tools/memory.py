import json
import re
from datetime import datetime, timezone
from pathlib import Path

from config import BOT_ROOT, bot_dir

PROMPT_PATH = Path(__file__).resolve().parent.parent / "instructions" / "prompts" / "memory.md"

ENTRY_PATTERN = re.compile(r"^- \[(m\d+)\] \(")
ENTRY_LINE = re.compile(r"^- \[(m\d+)\] \(([^)]*)\) (.+)$")


def memory_instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def make_memory_tools(profile: str | None) -> list:
    memory_path = (bot_dir(profile) or BOT_ROOT) / "MEMORY.md"

    def memory_text() -> str:
        try:
            return memory_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def parse_memory_entries(text: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for line in text.splitlines():
            match = ENTRY_LINE.match(line)
            if match:
                entry_id, timestamp, note = match.groups()
                entries.append({"id": entry_id, "time": timestamp, "note": note})
        return entries

    def next_entry_id(content: str) -> str:
        highest = 0
        for line in content.splitlines():
            match = ENTRY_PATTERN.match(line)
            if match:
                highest = max(highest, int(match.group(1)[1:]))
        return f"m{highest + 1}"

    def entry_id_of(line: str) -> str | None:
        match = ENTRY_PATTERN.match(line)
        return match.group(1).lower() if match else None

    def whoami() -> str:
        """Who are you? Returns the contents of your persistent memory.

        Returns a JSON array of objects, one per entry, with the fields 'id' (unique entry id such as 'm3'), 'time' (UTC timestamp of when the entry was saved, e.g. '2026-11-21T16:20:44Z') and 'note' (the remembered fact). Returns '[]' when memory is empty.
        """
        return json.dumps(parse_memory_entries(memory_text()), ensure_ascii=False)

    def remember(note: str) -> str:
        """Append a note to your persistent memory file so it is remembered across turns and sessions.

        The entry is stored with a unique id ('m<N>') and the time it was created. To change an entry, remember the new version, then forget the old one by its id.

        Args:
            note: The fact or preference to remember, one line.
        """
        note = " ".join(note.split())
        if not note:
            return "Nothing to remember: the note was empty."
        existing = memory_text()
        entry_id = next_entry_id(existing)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        with memory_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}- [{entry_id}] ({timestamp}) {note}\n")
        return f"Remembered [{entry_id}]: {note}"

    def forget(entry_id: str) -> str:
        """Remove the entry with the given id from your persistent memory file.

        Args:
            entry_id: The id of the entry to remove, like 'm3'; it is shown in whoami output.
        """
        target = entry_id.strip().lower()
        if not target:
            return "Nothing to forget: the id was empty."
        kept: list[str] = []
        removed: list[str] = []
        for line in memory_text().splitlines():
            if entry_id_of(line) == target:
                removed.append(line)
            else:
                kept.append(line)
        if not removed:
            return f"No memory entry with id '{entry_id.strip()}'."
        memory_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        return "Forgot:\n" + "\n".join(removed)

    return [whoami, remember, forget]
