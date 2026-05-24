"""Tests for album property reconciliation (description, sort_order,
thumbnail, comments_and_likes) — slice 8."""
import textwrap
import pytest
from unittest.mock import MagicMock
from immich_folder_organizer.config import AlbumConfig, load_config
from immich_folder_organizer.reconciler import reconcile_properties


def _config(**kwargs):
    return AlbumConfig(name="Album", paths=["/p"], **kwargs)


def _existing(description="", sort_order=None, is_activity_enabled=None, thumbnail=None):
    a = MagicMock()
    a.description = description
    a.order = sort_order
    a.is_activity_enabled = is_activity_enabled
    a.album_thumbnail_asset_id = thumbnail
    return a


# --- description ---

def test_declared_description_included_in_plan():
    config = _config(description="Ring Road")
    plan = reconcile_properties(config, existing=None, album_assets=[])
    assert plan.description is not None


def test_omitted_description_not_in_plan():
    config = _config()  # description=None
    plan = reconcile_properties(config, existing=None, album_assets=[])
    assert plan.description is None


def test_empty_description_clears_user_text():
    config = _config(description="")
    plan = reconcile_properties(config, existing=None, album_assets=[])
    # Empty string declared → plan includes description (to clear user text but keep marker)
    assert plan.description is not None


# --- sort_order ---

def test_declared_sort_order_included():
    config = _config(sort_order="asc")
    plan = reconcile_properties(config, existing=None, album_assets=[])
    assert plan.sort_order == "asc"


def test_omitted_sort_order_not_in_plan():
    config = _config()
    plan = reconcile_properties(config, existing=None, album_assets=[])
    assert plan.sort_order is None


# --- comments_and_likes ---

def test_declared_comments_and_likes_included():
    config = _config(comments_and_likes=True)
    plan = reconcile_properties(config, existing=None, album_assets=[])
    assert plan.is_activity_enabled is True


def test_omitted_comments_and_likes_not_in_plan():
    config = _config()
    plan = reconcile_properties(config, existing=None, album_assets=[])
    assert plan.is_activity_enabled is None


# --- thumbnail ---

def test_thumbnail_first_included():
    config = _config(thumbnail="first")
    assets = [MagicMock(id="a1"), MagicMock(id="a2")]
    plan = reconcile_properties(config, existing=None, album_assets=assets)
    assert plan.thumbnail_asset_id == "a1"


def test_thumbnail_last_included():
    config = _config(thumbnail="last")
    assets = [MagicMock(id="a1"), MagicMock(id="a2")]
    plan = reconcile_properties(config, existing=None, album_assets=assets)
    assert plan.thumbnail_asset_id == "a2"


def test_thumbnail_random_returns_an_id():
    config = _config(thumbnail="random")
    assets = [MagicMock(id="a1"), MagicMock(id="a2"), MagicMock(id="a3")]
    plan = reconcile_properties(config, existing=None, album_assets=assets)
    assert plan.thumbnail_asset_id in {"a1", "a2", "a3"}


def test_thumbnail_omitted_not_in_plan():
    config = _config()
    plan = reconcile_properties(config, existing=None, album_assets=[])
    assert plan.thumbnail_asset_id is None


# --- config parsing ---

def _yaml(text, tmp_path):
    p = tmp_path / "albums.yaml"
    p.write_text(textwrap.dedent(text))
    return str(p)


def test_config_parses_all_properties(tmp_path):
    path = _yaml(
        """
        albums:
          - name: "Iceland 2024"
            description: "Ring Road"
            sort_order: desc
            thumbnail: random
            comments_and_likes: true
            paths:
              - /photos/2024/Iceland
        """,
        tmp_path,
    )
    config = load_config(path)
    alb = config.albums[0]
    assert alb.description == "Ring Road"
    assert alb.sort_order == "desc"
    assert alb.thumbnail == "random"
    assert alb.comments_and_likes is True
