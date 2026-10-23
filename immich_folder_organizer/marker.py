import os
# Sentinel written into the description of every album created by this tool.
# Using a plain-text bracket form because Immich renders HTML comments visibly
# in the album description UI, which would leak as noise to the user.
MARKER = "[managed by immich-folder-organizer]"

_SEP = "\n"


def has_marker(description: str) -> bool:
    return MARKER in (description or "")


def with_marker(user_text: str) -> str:
    """Return description with the marker appended. Idempotent."""
    if has_marker(user_text):
        return user_text
    if user_text:
        return f"{user_text}{_SEP}{MARKER}"
    return MARKER


def extract_user_text(description: str) -> str:
    """Return the user-facing portion of a description, without the marker."""
    if not has_marker(description):
        return description
    idx = description.index(MARKER)
    return description[:idx].rstrip(_SEP)
