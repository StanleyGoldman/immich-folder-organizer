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
    client = _make_client(album_exists=False)
    executor = Executor(client, apply=True)

    with caplog.at_level(logging.INFO):
        result = executor.ensure_album("My Album")

    client.create_album.assert_called_once_with("My Album", "")
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
