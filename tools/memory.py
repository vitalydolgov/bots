import re
from datetime import datetime, timezone
from pathlib import Path

from config import BOT_ROOT, bot_dir

PROMPT_PATH = Path(__file__).resolve().parent.parent / "instructions" / "prompts" / "memory.md"

ENTRY_PATTERN = re.compile(r"^- \[(m\d+)\] \(")


def memory_instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def make_memory_tools(profile: str | None) -> list:
    memory_path = (bot_dir(profile) or BOT_ROOT) / "MEMORY.md"

    def read_memory_text() -> str:
        try:
            return memory_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def next_entry_id(content: str) -> str:
        highest = -1
        for line in content.splitlines():
            match = ENTRY_PATTERN.match(line)
            if match:
                highest = max(highest, int(match.group(1)[1:]))
        return f"m{highest + 1}"

    def entry_id_of(line: str) -> str | None:
        match = ENTRY_PATTERN.match(line)
        return match.group(1).lower() if match else None

    def read_memory() -> str:
        """Read the current contents of your persistent memory file.

        Each entry is shown as '- [m<N>] (<time>) <note>', where m<N> is the entry's id and the time is when it was created.
        """
        content = read_memory_text().strip()
        return content if content else "(memory is empty)"

    def remember(note: str) -> str:
        """Append a note to your persistent memory file so it is remembered across turns and sessions.

        The entry is stored with a unique id ('m<N>') and the time it was created.

        Args:
            note: The fact or preference to remember, one line.
        """
        note = " ".join(note.split())
        if not note:
            return "Nothing to remember: the note was empty."
        existing = read_memory_text()
        entry_id = next_entry_id(existing)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        with memory_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}- [{entry_id}] ({timestamp}) {note}\n")
        return f"Remembered [{entry_id}]: {note}"

    def forget(entry_id: str) -> str:
        """Remove the entry with the given id from your persistent memory file.

        Args:
            entry_id: The id of the entry to remove, like 'm3'; it is shown in read_memory output.
        """
        target = entry_id.strip().lower()
        if not target:
            return "Nothing to forget: the id was empty."
        kept: list[str] = []
        removed: list[str] = []
        for line in read_memory_text().splitlines():
            if entry_id_of(line) == target:
                removed.append(line)
            else:
                kept.append(line)
        if not removed:
            return f"No memory entry with id '{entry_id.strip()}'."
        memory_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        return "Forgot:\n" + "\n".join(removed)

    def write_memory(content: str) -> str:
        """Replace the whole contents of your persistent memory file, for editing or removing existing entries.

        Args:
            content: The full new contents of your persistent memory file.
        """
        memory_path.write_text(content if content.endswith("\n") or not content else content + "\n", encoding="utf-8")
        return "Memory updated."

    return [read_memory, remember, forget, write_memory]
