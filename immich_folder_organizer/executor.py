import logging

from .marker import has_marker, with_marker

log = logging.getLogger(__name__)


class Executor:
    def __init__(self, client, apply: bool):
        self._client = client
        self._apply = apply

    def ensure_album(self, name: str, user_description: str = "") -> str:
        """Return album id, creating or adopting as needed. Writes marker."""
        existing = self._client.get_album_by_name(name)

        if existing is None:
            description = with_marker(user_description)
            if self._apply:
                album = self._client.create_album(name, description)
                log.info("[create] Album created with marker: '%s'", name)
                return album.id
            else:
                log.info("[dry-run] Would create album: '%s'", name)
                return None

        if not has_marker(existing.description or ""):
            # Adoption: pre-existing un-marked album
            log.warning(
                "[adopt] Album '%s' exists without marker — adopting it under tool management",
                name,
            )
            new_description = with_marker(existing.description or "")
            if self._apply:
                self._client.update_album(existing.id, description=new_description)
                log.info("[adopt] Marker added to '%s'", name)
            else:
                log.info("[dry-run] Would adopt album '%s'", name)

        log.info("[manage] Album '%s' is tool-managed", name)
        return existing.id

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
