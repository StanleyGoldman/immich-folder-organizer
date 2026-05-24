from typing import Optional


def _matches_prefix(asset_path: str, prefix: str) -> bool:
    """True when asset_path is equal to prefix or is a descendant of it."""
    if asset_path == prefix:
        return True
    return asset_path.startswith(prefix.rstrip("/") + "/")


def is_member(asset_path: str, includes: list, excludes: Optional[list] = None) -> bool:
    """Return True if asset_path is under any include path and not under any exclude path."""
    if not any(_matches_prefix(asset_path, inc) for inc in includes):
        return False
    if excludes:
        if any(_matches_prefix(asset_path, exc) for exc in excludes):
            return False
    return True
