import logging

log = logging.getLogger(__name__)


class Executor:
    def __init__(self, client, apply: bool):
        self._client = client
        self._apply = apply

    def ensure_album(self, name: str, description: str = "") -> str:
        """Return album id, creating the album if it does not exist."""
        existing = self._client.get_album_by_name(name)
        if existing is not None:
            log.info("[no-op] Album already exists: %s", name)
            return existing.id

        if self._apply:
            album = self._client.create_album(name, description)
            log.info("[create] Album created: %s", name)
            return album.id
        else:
            log.info("[dry-run] Would create album: %s", name)
            return None
