from dataclasses import dataclass, field
from typing import Optional

from .path_matcher import is_member


@dataclass
class AlbumPlan:
    to_add: list = field(default_factory=list)
    to_remove: list = field(default_factory=list)


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
