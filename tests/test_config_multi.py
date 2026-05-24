"""Tests for multi-album, multi-path config parsing (slice 5)."""
import textwrap
import pytest
from immich_folder_organizer.config import load_config


def _yaml(text, tmp_path):
    p = tmp_path / "albums.yaml"
    p.write_text(textwrap.dedent(text))
    return str(p)


def test_multiple_albums_parsed(tmp_path):
    path = _yaml(
        """
        albums:
          - name: "Album A"
            paths:
              - /photos/a
          - name: "Album B"
            paths:
              - /photos/b
          - name: "Album C"
            paths:
              - /photos/c
        """,
        tmp_path,
    )
    config = load_config(path)
    assert len(config.albums) == 3
    assert config.albums[0].name == "Album A"
    assert config.albums[2].name == "Album C"


def test_multiple_paths_per_album(tmp_path):
    path = _yaml(
        """
        albums:
          - name: "Vacations"
            paths:
              - /photos/italy
              - /photos/japan
              - /photos/spain
        """,
        tmp_path,
    )
    config = load_config(path)
    assert config.albums[0].paths == ["/photos/italy", "/photos/japan", "/photos/spain"]
