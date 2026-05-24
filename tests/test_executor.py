import io
import logging
import pytest
from unittest.mock import MagicMock
from immich_folder_organizer.executor import Executor


def _make_client(album_exists=False):
    client = MagicMock()
    if album_exists:
        album = MagicMock()
        album.id = "existing-id"
        album.album_name = "My Album"
        client.get_album_by_name.return_value = album
    else:
        client.get_album_by_name.return_value = None
        new_album = MagicMock()
        new_album.id = "new-id"
        client.create_album.return_value = new_album
    return client


def test_dry_run_does_not_call_create(caplog):
    client = _make_client(album_exists=False)
    executor = Executor(client, apply=False)

    with caplog.at_level(logging.INFO):
        result = executor.ensure_album("My Album")

    client.create_album.assert_not_called()
    assert result is None
    assert "dry-run" in caplog.text.lower() or "DRY" in caplog.text


def test_apply_creates_album(caplog):
    from immich_folder_organizer.marker import MARKER

    client = _make_client(album_exists=False)
    executor = Executor(client, apply=True)

    with caplog.at_level(logging.INFO):
        result = executor.ensure_album("My Album")

    client.create_album.assert_called_once()
    _, call_desc = client.create_album.call_args[0]
    assert MARKER in call_desc
    assert result == "new-id"


def test_existing_album_is_no_op(caplog):
    client = _make_client(album_exists=True)
    executor = Executor(client, apply=True)

    with caplog.at_level(logging.INFO):
        result = executor.ensure_album("My Album")

    client.create_album.assert_not_called()
    assert result == "existing-id"


def test_dry_run_existing_album_is_no_op():
    client = _make_client(album_exists=True)
    executor = Executor(client, apply=False)
    result = executor.ensure_album("My Album")
    client.create_album.assert_not_called()
    assert result == "existing-id"


def _make_plan(to_add=None, to_remove=None):
    plan = MagicMock()
    plan.to_add = to_add or []
    plan.to_remove = to_remove or []
    return plan


def test_sync_assets_apply_add():
    client = MagicMock()
    executor = Executor(client, apply=True)
    plan = _make_plan(to_add=["a1", "a2"])

    executor.sync_assets("alb-id", "My Album", plan)

    client.add_assets.assert_called_once_with("alb-id", ["a1", "a2"])
    client.remove_assets.assert_not_called()


def test_sync_assets_apply_remove():
    client = MagicMock()
    executor = Executor(client, apply=True)
    plan = _make_plan(to_remove=["r1"])

    executor.sync_assets("alb-id", "My Album", plan)

    client.remove_assets.assert_called_once_with("alb-id", ["r1"])
    client.add_assets.assert_not_called()


def test_ensure_album_adopts_unmarked_existing(caplog):
    from immich_folder_organizer.marker import MARKER

    client = MagicMock()
    existing = MagicMock()
    existing.id = "alb-id"
    existing.description = "Plain description"
    client.get_album_by_name.return_value = existing

    executor = Executor(client, apply=True)
    with caplog.at_level(logging.WARNING):
        result = executor.ensure_album("My Album")

    # Must update description with marker
    client.update_album.assert_called_once()
    _, kwargs = client.update_album.call_args
    assert MARKER in kwargs["description"]
    assert result == "alb-id"
    assert "adopt" in caplog.text.lower()


def test_ensure_album_dry_run_adopts_without_update(caplog):
    from immich_folder_organizer.marker import MARKER

    client = MagicMock()
    existing = MagicMock()
    existing.id = "alb-id"
    existing.description = "Plain"
    client.get_album_by_name.return_value = existing

    executor = Executor(client, apply=False)
    with caplog.at_level(logging.WARNING):
        result = executor.ensure_album("My Album")

    client.update_album.assert_not_called()
    assert result == "alb-id"


def test_ensure_album_marked_album_no_update(caplog):
    from immich_folder_organizer.marker import with_marker

    client = MagicMock()
    existing = MagicMock()
    existing.id = "alb-id"
    existing.description = with_marker("Existing description")
    client.get_album_by_name.return_value = existing

    executor = Executor(client, apply=True)
    executor.ensure_album("My Album")

    client.create_album.assert_not_called()
    client.update_album.assert_not_called()


def test_sync_assets_dry_run_no_api_calls():
    client = MagicMock()
    executor = Executor(client, apply=False)
    plan = _make_plan(to_add=["a1"], to_remove=["r1"])

    executor.sync_assets("alb-id", "My Album", plan)

    client.add_assets.assert_not_called()
    client.remove_assets.assert_not_called()
