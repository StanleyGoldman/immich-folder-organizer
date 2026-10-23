import logging
from uuid import UUID

from .marker import has_marker, with_marker

log = logging.getLogger(__name__)


class Executor:
    def __init__(self, client, apply: bool):
        self._client = client
        self._apply = apply

    def ensure_album(self, name: str, user_description: str = "") -> UUID | None:
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

    def sync_properties(
        self, album_id: UUID | None, album_name: str, prop_plan
    ) -> None:
        """Apply or preview declared album properties."""
        updates = {}
        if prop_plan.description is not None:
            updates["description"] = prop_plan.description
        if prop_plan.sort_order is not None:
            updates["sort_order"] = prop_plan.sort_order
        if prop_plan.is_activity_enabled is not None:
            updates["is_activity_enabled"] = prop_plan.is_activity_enabled
        if prop_plan.thumbnail_asset_id is not None:
            updates["thumbnail_asset_id"] = prop_plan.thumbnail_asset_id

        if not updates:
            return

        if self._apply:
            self._client.update_album(album_id, **updates)
            log.info(
                "[props] Updated properties of '%s': %s", album_name, list(updates)
            )
        else:
            log.info(
                "[dry-run] Would update properties of '%s': %s",
                album_name,
                list(updates),
            )

    def sync_shares(self, album_id: UUID | None, album_name: str, share_plan) -> None:
        """Apply or preview share additions and revocations."""
        if share_plan.skip:
            return

        for ref in share_plan.missing_users:
            log.warning("[shares] User '%s' not found in Immich — skipping", ref)

        for user_id, role in share_plan.to_add:
            if self._apply:
                self._client.share_album(album_id, user_id, role)
                log.info("[share] Shared '%s' with %s as %s", album_name, user_id, role)
            else:
                log.info(
                    "[dry-run] Would share '%s' with %s as %s",
                    album_name,
                    user_id,
                    role,
                )

        for user_id in share_plan.to_remove:
            if self._apply:
                self._client.revoke_share(album_id, user_id)
                log.info("[share] Revoked access of %s from '%s'", user_id, album_name)
            else:
                log.info(
                    "[dry-run] Would revoke access of %s from '%s'", user_id, album_name
                )

    def delete_orphaned_album(self, album_id: UUID, album_name: str) -> None:
        if self._apply:
            self._client.delete_album(album_id)
            log.info("[delete] Orphaned album deleted: '%s'", album_name)
        else:
            log.info("[dry-run] Would delete orphaned album: '%s'", album_name)

    def sync_assets(self, album_id: UUID | None, album_name: str, plan) -> None:
        """Apply or preview the asset add/remove plan for one album."""
        if plan.to_add:
            if self._apply:
                self._client.add_assets(album_id, plan.to_add)
                log.info(
                    "[add] %d asset(s) added to '%s'", len(plan.to_add), album_name
                )
            else:
                log.info(
                    "[dry-run] Would add %d asset(s) to '%s'",
                    len(plan.to_add),
                    album_name,
                )

        if plan.to_remove:
            if self._apply:
                self._client.remove_assets(album_id, plan.to_remove)
                log.info(
                    "[remove] %d asset(s) removed from '%s'",
                    len(plan.to_remove),
                    album_name,
                )
            else:
                log.info(
                    "[dry-run] Would remove %d asset(s) from '%s'",
                    len(plan.to_remove),
                    album_name,
                )
