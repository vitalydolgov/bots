from pathlib import Path

from config import PROFILES_DIR, PROFILE_PATTERN

PROMPTS_DIR = Path(__file__).resolve().parent / "instructions" / "prompts"


def roster_instructions() -> str:
    profiles_dir = PROFILES_DIR
    try:
        names = sorted(
            entry.name
            for entry in profiles_dir.iterdir()
            if entry.is_dir() and PROFILE_PATTERN.fullmatch(entry.name)
        )
    except (FileNotFoundError, NotADirectoryError):
        return ""
    if not names:
        return ""
    listing = "\n".join(f"  - {name}" for name in names)
    return (PROMPTS_DIR / "roster.md").read_text(encoding="utf-8").strip().format(names=listing)
