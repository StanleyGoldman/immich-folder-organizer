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
