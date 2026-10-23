"""Tests for share_with reconciliation (slice 9)."""
import textwrap
import pytest
from unittest.mock import MagicMock
from immich_folder_organizer.config import AlbumConfig, ShareEntry, load_config
from immich_folder_organizer.reconciler import reconcile_shares


def _user(id, name, email):
    u = MagicMock()
    u.id = id
    u.name = name
    u.email = email
    return u


def _album_user(user_id, role):
    au = MagicMock()
    au.user = MagicMock()
    au.user.id = user_id
    au.role = role
    return au


def _config(share_with=None):
    return AlbumConfig(name="Test", paths=["/p"], share_with=share_with)


ALL_USERS = [
    _user("u1", "alice", "alice@example.com"),
    _user("u2", "bob", "bob@example.com"),
]


def test_share_add_by_username():
    config = _config(share_with=[ShareEntry(user="alice", role="viewer")])
    plan = reconcile_shares(config, current_shares=[], all_users=ALL_USERS)
    assert ("u1", "viewer") in plan.to_add


def test_share_add_by_email():
    config = _config(share_with=[ShareEntry(user="bob@example.com", role="editor")])
    plan = reconcile_shares(config, current_shares=[], all_users=ALL_USERS)
    assert ("u2", "editor") in plan.to_add


def test_role_defaults_to_viewer():
    config = _config(share_with=[ShareEntry(user="alice")])
    plan = reconcile_shares(config, current_shares=[], all_users=ALL_USERS)
    assert ("u1", "viewer") in plan.to_add


def test_share_remove_manual_share():
    """Manually-added share not in YAML is revoked."""
    config = _config(share_with=[ShareEntry(user="alice", role="viewer")])
    current = [_album_user("u2", "viewer")]  # bob manually added — not in YAML
    plan = reconcile_shares(config, current_shares=current, all_users=ALL_USERS)
    assert "u2" in plan.to_remove


def test_empty_share_with_removes_all():
    config = _config(share_with=[])
    current = [_album_user("u1", "viewer"), _album_user("u2", "editor")]
    plan = reconcile_shares(config, current_shares=current, all_users=ALL_USERS)
    assert set(plan.to_remove) == {"u1", "u2"}
    assert plan.to_add == []


def test_album_owner_is_never_revoked():
    """Immich v3 lists the album owner among the album users, as role owner."""
    config = _config(share_with=[])
    current = [_album_user("owner-id", "owner"), _album_user("u1", "viewer")]
    plan = reconcile_shares(config, current_shares=current, all_users=ALL_USERS)
    assert plan.to_remove == ["u1"]
    assert plan.to_add == []


def test_omit_share_with_skips_reconciliation():
    """share_with=None means do not touch shares."""
    config = _config(share_with=None)
    plan = reconcile_shares(config, current_shares=[], all_users=ALL_USERS)
    assert plan.skip is True


def test_no_change_when_already_correct():
    config = _config(share_with=[ShareEntry(user="alice", role="viewer")])
    current = [_album_user("u1", "viewer")]
    plan = reconcile_shares(config, current_shares=current, all_users=ALL_USERS)
    assert plan.to_add == []
    assert plan.to_remove == []


def test_missing_user_skipped_not_fatal():
    config = _config(share_with=[ShareEntry(user="nobody@example.com", role="viewer")])
    plan = reconcile_shares(config, current_shares=[], all_users=ALL_USERS)
    assert plan.to_add == []
    assert plan.missing_users == ["nobody@example.com"]


def _yaml(text, tmp_path):
    p = tmp_path / "albums.yaml"
    p.write_text(textwrap.dedent(text))
    return str(p)


def test_config_parses_share_with(tmp_path):
    path = _yaml(
        """
        albums:
          - name: "Shared"
            paths:
              - /photos
            share_with:
              - user: alice
                role: editor
              - user: friend@example.com
        """,
        tmp_path,
    )
    config = load_config(path)
    alb = config.albums[0]
    assert alb.share_with[0].user == "alice"
    assert alb.share_with[0].role == "editor"
    assert alb.share_with[1].user == "friend@example.com"
    assert alb.share_with[1].role == "viewer"  # default
