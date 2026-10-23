"""Tests for orphan album deletion (slice 10)."""

import textwrap
from unittest.mock import MagicMock

from immich_folder_organizer.config import load_config
from immich_folder_organizer.marker import with_marker
from immich_folder_organizer.reconciler import find_orphaned_albums


def _album(name, description=""):
    a = MagicMock()
    a.id = f"id-{name}"
    a.album_name = name
    a.description = description
    return a


def _declared_names(*names):
    return set(names)


def test_orphan_detection_marked_missing_album():
    albums = [_album("Orphan", with_marker(""))]
    declared = _declared_names("Active")
    orphans = find_orphaned_albums(albums, declared)
    assert len(orphans) == 1
    assert orphans[0].album_name == "Orphan"


def test_declared_album_not_orphaned():
    albums = [_album("Active", with_marker(""))]
    declared = _declared_names("Active")
    orphans = find_orphaned_albums(albums, declared)
    assert orphans == []


def test_unmarked_album_never_orphaned():
    albums = [_album("Manual", "plain description")]
    declared = _declared_names()
    orphans = find_orphaned_albums(albums, declared)
    assert orphans == []


def test_unmarked_album_with_delete_flag_still_not_deleted():
    """Even with delete_orphaned_albums=True, unmarked albums are never touched."""
    albums = [_album("Manual", "plain")]
    declared = _declared_names()
    orphans = find_orphaned_albums(albums, declared)
    assert orphans == []


def test_multiple_orphans_found():
    albums = [
        _album("Orphan1", with_marker("")),
        _album("Orphan2", with_marker("some text")),
        _album("Active", with_marker("")),
    ]
    declared = _declared_names("Active")
    orphans = find_orphaned_albums(albums, declared)
    assert {o.album_name for o in orphans} == {"Orphan1", "Orphan2"}


def _yaml(text, tmp_path):
    p = tmp_path / "albums.yaml"
    p.write_text(textwrap.dedent(text))
    return str(p)


def test_config_delete_orphaned_false_by_default(tmp_path):
    path = _yaml(
        """
        albums:
          - name: "Test"
            paths:
              - /photos
        """,
        tmp_path,
    )
    config = load_config(path)
    assert config.delete_orphaned_albums is False


def test_config_delete_orphaned_true_when_set(tmp_path):
    path = _yaml(
        """
        delete_orphaned_albums: true
        albums:
          - name: "Test"
            paths:
              - /photos
        """,
        tmp_path,
    )
    config = load_config(path)
    assert config.delete_orphaned_albums is True
