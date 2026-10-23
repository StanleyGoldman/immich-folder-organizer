import random as _random
from dataclasses import dataclass, field
from uuid import UUID

from .immich_client import AlbumUserRole
from .marker import has_marker, with_marker
from .path_matcher import is_member


@dataclass
class AlbumPlan:
    to_add: list = field(default_factory=list)
    to_remove: list = field(default_factory=list)


@dataclass
class SharePlan:
    skip: bool = False
    to_add: list = field(default_factory=list)  # list of (user_id, role) tuples
    to_remove: list = field(default_factory=list)  # list of user IDs
    missing_users: list = field(default_factory=list)


@dataclass
class AlbumStatePlan:
    create: bool = False
    adopt: bool = False
    album_id: UUID | None = None


@dataclass
class PropertyPlan:
    description: str | None = None
    sort_order: str | None = None
    is_activity_enabled: bool | None = None
    thumbnail_asset_id: UUID | None = None


def reconcile_album_state(album_config, existing_album) -> AlbumStatePlan:
    """Determine whether to create a new album, adopt an existing one, or manage normally."""
    if existing_album is None:
        return AlbumStatePlan(create=True)

    if has_marker(existing_album.description or ""):
        return AlbumStatePlan(create=False, adopt=False, album_id=existing_album.id)

    return AlbumStatePlan(create=False, adopt=True, album_id=existing_album.id)


def reconcile_properties(album_config, existing, album_assets: list) -> PropertyPlan:
    """Compute which album properties need to be written based on YAML declaration.

    Only fields declared in YAML (non-None) are included in the plan.
    """
    plan = PropertyPlan()

    # description — declared (even as "") means we should write it
    if album_config.description is not None:
        plan.description = with_marker(album_config.description)

    if album_config.sort_order is not None:
        plan.sort_order = album_config.sort_order

    if album_config.comments_and_likes is not None:
        plan.is_activity_enabled = album_config.comments_and_likes

    if album_config.thumbnail is not None:
        plan.thumbnail_asset_id = _resolve_thumbnail(
            album_config.thumbnail, album_assets
        )

    return plan


def _resolve_thumbnail(setting: str, album_assets: list) -> UUID | None:
    if not album_assets:
        return None
    if setting == "first":
        return album_assets[0].id
    if setting == "last":
        return album_assets[-1].id
    if setting == "random":
        return _random.choice(album_assets).id
    # Absolute asset path — find matching asset
    for asset in album_assets:
        if asset.original_path == setting:
            return asset.id
    return None


def reconcile_shares(album_config, current_shares: list, all_users: list) -> SharePlan:
    """Compute share additions and removals. Returns skip=True when share_with is omitted."""
    if album_config.share_with is None:
        return SharePlan(skip=True)

    def _resolve_user(ref: str):
        for u in all_users:
            if u.name == ref or u.email == ref:
                return u
        return None

    desired = {}  # user_id -> role
    missing = []
    for entry in album_config.share_with:
        user = _resolve_user(entry.user)
        if user is None:
            missing.append(entry.user)
            continue
        desired[user.id] = entry.role

    # Immich lists the album owner among its users; ownership isn't a share
    current = {
        au.user.id: au.role for au in current_shares if au.role != AlbumUserRole.OWNER
    }

    to_add = [
        (uid, role)
        for uid, role in desired.items()
        if uid not in current or current[uid] != role
    ]
    to_remove = [uid for uid in current if uid not in desired]

    return SharePlan(to_add=to_add, to_remove=to_remove, missing_users=missing)


def find_orphaned_albums(all_albums: list, declared_names: set) -> list:
    """Return marker-bearing albums whose names are not in declared_names."""
    return [
        album
        for album in all_albums
        if album.album_name not in declared_names
        and has_marker(album.description or "")
    ]


def reconcile(album_config, current_ids: list, all_assets: list) -> AlbumPlan:
    """Compute which assets to add and remove for a single album."""
    matching_ids = {
        a.id
        for a in all_assets
        if is_member(a.original_path, album_config.paths, album_config.exclude)
    }
    current_set = set(current_ids)

    to_add = sorted(matching_ids - current_set)
    to_remove = sorted(current_set - matching_ids)

    return AlbumPlan(to_add=to_add, to_remove=to_remove)
