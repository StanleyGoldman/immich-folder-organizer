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

    def sync_assets(self, album_id: str, album_name: str, plan) -> None:
        """Apply or preview the asset add/remove plan for one album."""
        if plan.to_add:
            if self._apply:
                self._client.add_assets(album_id, plan.to_add)
                log.info("[add] %d asset(s) added to '%s'", len(plan.to_add), album_name)
            else:
                log.info("[dry-run] Would add %d asset(s) to '%s'", len(plan.to_add), album_name)

        if plan.to_remove:
            if self._apply:
                self._client.remove_assets(album_id, plan.to_remove)
                log.info("[remove] %d asset(s) removed from '%s'", len(plan.to_remove), album_name)
            else:
                log.info("[dry-run] Would remove %d asset(s) from '%s'", len(plan.to_remove), album_name)
