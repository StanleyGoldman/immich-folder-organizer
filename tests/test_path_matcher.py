import pytest
from immich_folder_organizer.path_matcher import is_member


def test_direct_child_is_member():
    assert is_member("/a/photo.jpg", ["/a"])


def test_deep_nested_is_member():
    assert is_member("/a/b/c/photo.jpg", ["/a"])


def test_sibling_prefix_not_member():
    assert not is_member("/abc/photo.jpg", ["/a"])


def test_exact_path_match_is_member():
    assert is_member("/a", ["/a"])


def test_no_include_match_not_member():
    assert not is_member("/x/photo.jpg", ["/a", "/b"])


def test_multiple_includes_any_match():
    assert is_member("/b/photo.jpg", ["/a", "/b"])


def test_exclude_wins_over_include():
    assert not is_member("/a/private/photo.jpg", ["/a"], excludes=["/a/private"])


def test_not_under_exclude_is_included():
    assert is_member("/a/public/photo.jpg", ["/a"], excludes=["/a/private"])


def test_excludes_none_is_same_as_empty():
    assert is_member("/a/photo.jpg", ["/a"], excludes=None)


def test_asset_is_exclude_prefix_only_not_excluded():
    # /abcdef should NOT be excluded by /abc
    assert is_member("/abcdef/photo.jpg", ["/abcdef"], excludes=["/abc"])


def test_under_exclude_but_not_include_still_excluded():
    assert not is_member("/a/private/photo.jpg", ["/b"], excludes=["/a/private"])


def test_multiple_excludes_any_match_excludes():
    assert not is_member("/a/x/photo.jpg", ["/a"], excludes=["/a/y", "/a/x"])


def test_empty_excludes_list_no_exclusion():
    assert is_member("/a/photo.jpg", ["/a"], excludes=[])
