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
    current_ids = [
        "2"
    ]  # has asset that should be removed, missing one that should be added

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


def test_multiple_paths_union_of_assets():
    config = _album_config(["/path1", "/path2"])
    all_assets = [
        _asset("1", "/path1/a.jpg"),
        _asset("2", "/path2/b.jpg"),
        _asset("3", "/other/c.jpg"),
    ]
    plan = reconcile(config, [], all_assets)
    assert set(plan.to_add) == {"1", "2"}


def test_multiple_paths_no_double_add():
    config = _album_config(["/a", "/a/sub"])
    all_assets = [_asset("1", "/a/sub/photo.jpg")]
    # Asset matches both /a and /a/sub but should only appear once in to_add
    plan = reconcile(config, [], all_assets)
    assert plan.to_add == ["1"]


def test_exclude_removes_matching_asset():
    config = _album_config(["/photos"], exclude=["/photos/private"])
    all_assets = [
        _asset("1", "/photos/a.jpg"),
        _asset("2", "/photos/private/b.jpg"),
    ]
    plan = reconcile(config, [], all_assets)
    assert plan.to_add == ["1"]


def test_exclude_wins_over_include():
    config = _album_config(["/a"], exclude=["/a/b"])
    all_assets = [_asset("1", "/a/b/photo.jpg")]
    plan = reconcile(config, [], all_assets)
    assert plan.to_add == []


def test_shared_asset_across_albums_reconciled_independently():
    """Shared asset (two albums, same path) — each album is reconciled separately."""
    shared_asset = _asset("shared", "/vacation/photo.jpg")
    all_assets = [shared_asset]

    config_a = _album_config(["/vacation"])
    config_b = _album_config(["/vacation"])

    plan_a = reconcile(config_a, [], all_assets)
    plan_b = reconcile(config_b, [], all_assets)

    assert plan_a.to_add == ["shared"]
    assert plan_b.to_add == ["shared"]


def test_reconcile_markers_new_album_has_marker():
    """reconcile_album_state detects no album → create=True."""
    from immich_folder_organizer.reconciler import reconcile_album_state

    config = _album_config(["/photos"])
    plan = reconcile_album_state(config, existing_album=None)
    assert plan.create is True
    assert plan.adopt is False


def test_reconcile_markers_managed_album_recognized():
    from immich_folder_organizer.marker import with_marker
    from immich_folder_organizer.reconciler import reconcile_album_state

    existing = MagicMock()
    existing.id = "alb-1"
    existing.description = with_marker("User description")

    config = _album_config(["/photos"])
    plan = reconcile_album_state(config, existing_album=existing)
    assert plan.create is False
    assert plan.adopt is False


def test_reconcile_markers_unmarked_album_triggers_adoption():
    from immich_folder_organizer.reconciler import reconcile_album_state

    existing = MagicMock()
    existing.id = "alb-1"
    existing.description = "Manually created album"

    config = _album_config(["/photos"])
    plan = reconcile_album_state(config, existing_album=existing)
    assert plan.create is False
    assert plan.adopt is True
