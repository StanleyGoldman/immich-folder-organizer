import pytest
from unittest.mock import MagicMock
from immich_folder_organizer.config import AlbumConfig
from immich_folder_organizer.reconciler import reconcile


def _asset(id, path):
    a = MagicMock()
    a.id = id
    a.original_path = path
    return a


def _album_config(paths, exclude=None):
    return AlbumConfig(name="Test", paths=paths, exclude=exclude or [])


def test_empty_album_all_matching_added():
    config = _album_config(["/photos"])
    all_assets = [_asset("1", "/photos/a.jpg"), _asset("2", "/photos/b.jpg")]
    current_ids = []

    plan = reconcile(config, current_ids, all_assets)

    assert set(plan.to_add) == {"1", "2"}
    assert plan.to_remove == []


def test_partial_overlap_only_missing_added():
    config = _album_config(["/photos"])
    all_assets = [_asset("1", "/photos/a.jpg"), _asset("2", "/photos/b.jpg")]
    current_ids = ["1"]

    plan = reconcile(config, current_ids, all_assets)

    assert plan.to_add == ["2"]
    assert plan.to_remove == []


def test_already_complete_is_no_op():
    config = _album_config(["/photos"])
    all_assets = [_asset("1", "/photos/a.jpg"), _asset("2", "/photos/b.jpg")]
    current_ids = ["1", "2"]

    plan = reconcile(config, current_ids, all_assets)

    assert plan.to_add == []
    assert plan.to_remove == []


def test_asset_not_under_path_not_added():
    config = _album_config(["/photos"])
    all_assets = [_asset("1", "/other/a.jpg")]
    current_ids = []

    plan = reconcile(config, current_ids, all_assets)

    assert plan.to_add == []
    assert plan.to_remove == []


def test_sibling_prefix_not_included():
    config = _album_config(["/a"])
    all_assets = [_asset("1", "/abc/x.jpg")]
    current_ids = []

    plan = reconcile(config, current_ids, all_assets)

    assert plan.to_add == []


def test_asset_in_album_not_under_path_is_removed():
    config = _album_config(["/photos"])
    all_assets = [_asset("1", "/photos/a.jpg"), _asset("2", "/other/b.jpg")]
    current_ids = ["1", "2"]  # 2 is in album but not under /photos

    plan = reconcile(config, current_ids, all_assets)

    assert plan.to_add == []
    assert plan.to_remove == ["2"]


def test_full_diff_add_and_remove():
    config = _album_config(["/photos"])
    all_assets = [_asset("1", "/photos/a.jpg"), _asset("2", "/other/b.jpg")]
    current_ids = ["2"]  # has asset that should be removed, missing one that should be added

    plan = reconcile(config, current_ids, all_assets)

    assert plan.to_add == ["1"]
    assert plan.to_remove == ["2"]


def test_tool_wins_manually_added_asset_removed():
    """Assets added manually in Immich UI that don't match paths are removed."""
    config = _album_config(["/managed"])
    all_assets = [_asset("1", "/managed/a.jpg"), _asset("manual", "/elsewhere/m.jpg")]
    current_ids = ["1", "manual"]

    plan = reconcile(config, current_ids, all_assets)

    assert plan.to_add == []
    assert plan.to_remove == ["manual"]


def test_no_spurious_removes():
    config = _album_config(["/photos"])
    all_assets = [_asset("1", "/photos/a.jpg"), _asset("2", "/photos/b.jpg")]
    current_ids = ["1", "2"]

    plan = reconcile(config, current_ids, all_assets)

    assert plan.to_remove == []
