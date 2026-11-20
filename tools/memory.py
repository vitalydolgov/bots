from pathlib import Path

from config import BOT_ROOT, bot_dir

PROMPT_PATH = Path(__file__).resolve().parent.parent / "instructions" / "prompts" / "memory.md"


def memory_instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def make_memory_tools(profile: str | None) -> list:
    memory_path = (bot_dir(profile) or BOT_ROOT) / "MEMORY.md"

    def read_memory_text() -> str:
        try:
            return memory_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def read_memory() -> str:
        """Read the current contents of your persistent memory file."""
        content = read_memory_text().strip()
        return content if content else "(memory is empty)"

    def remember(note: str) -> str:
        """Append a note to your persistent memory file so it is remembered across turns and sessions.

        Args:
            note: The fact or preference to remember, one line.
        """
        note = note.strip()
        if not note:
            return "Nothing to remember: the note was empty."
        existing = read_memory_text()
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        with memory_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}- {note}\n")
        return f"Remembered: {note}"

    def forget(note: str) -> str:
        """Remove entries from your persistent memory file that match the given text.

        Args:
            note: Text identifying the entries to forget; every line containing this text (case-insensitive) is removed.
        """
        query = " ".join(note.split()).lower()
        if not query:
            return "Nothing to forget: the query was empty."
        kept: list[str] = []
        removed: list[str] = []
        for line in read_memory_text().splitlines():
            if query in line.lower():
                removed.append(line)
            else:
                kept.append(line)
        if not removed:
            return f"No memory entries match '{note.strip()}'."
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
