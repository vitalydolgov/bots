from datetime import datetime


def current_datetime() -> str:
    """Return the current local date and time with timezone, in ISO 8601 format."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


DATE_TOOLS = [current_datetime]
