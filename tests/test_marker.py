from immich_folder_organizer.marker import (
    MARKER,
    extract_user_text,
    has_marker,
    with_marker,
)


def test_has_marker_detects_marker():
    assert has_marker(f"Some description\n{MARKER}")


def test_has_marker_detects_marker_only():
    assert has_marker(MARKER)


def test_has_marker_false_when_absent():
    assert not has_marker("Some plain description")


def test_has_marker_false_on_empty():
    assert not has_marker("")


def test_with_marker_appends_marker():
    result = with_marker("My description")
    assert MARKER in result
    assert "My description" in result


def test_with_marker_empty_user_text():
    result = with_marker("")
    assert MARKER in result


def test_with_marker_is_idempotent():
    first = with_marker("Hello")
    second = with_marker(first)
    # applying twice should not double-append the marker
    assert second.count(MARKER) == 1


def test_round_trip_preserves_user_text():
    original = "Ring Road, September 2024"
    marked = with_marker(original)
    assert extract_user_text(marked) == original


def test_extract_user_text_no_marker():
    assert extract_user_text("plain text") == "plain text"


def test_extract_user_text_empty_user_text():
    marked = with_marker("")
    assert extract_user_text(marked) == ""


def test_with_marker_idempotent_user_text_preserved():
    original = "My Album"
    first = with_marker(original)
    second = with_marker(first)
    assert extract_user_text(second) == original
