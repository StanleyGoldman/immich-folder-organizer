import textwrap

import pytest

from immich_folder_organizer.config import ConfigError, load_config, load_env


def _yaml(text, tmp_path):
    p = tmp_path / "albums.yaml"
    p.write_text(textwrap.dedent(text))
    return str(p)


def test_load_config_minimal(tmp_path):
    path = _yaml(
        """
        albums:
          - name: "Italy 2023"
            paths:
              - /photos/2023/Italy
        """,
        tmp_path,
    )
    config = load_config(path)
    assert len(config.albums) == 1
    assert config.albums[0].name == "Italy 2023"
    assert config.albums[0].paths == ["/photos/2023/Italy"]


def test_load_config_missing_name_raises(tmp_path):
    path = _yaml(
        """
        albums:
          - paths:
              - /photos/2023
        """,
        tmp_path,
    )
    with pytest.raises(ConfigError, match="name"):
        load_config(path)


def test_load_config_missing_paths_raises(tmp_path):
    path = _yaml(
        """
        albums:
          - name: "Italy 2023"
        """,
        tmp_path,
    )
    with pytest.raises(ConfigError, match="paths"):
        load_config(path)


def test_load_env_missing_url_raises(monkeypatch):
    monkeypatch.delenv("IMMICH_URL", raising=False)
    monkeypatch.setenv("IMMICH_API_KEY", "key")
    with pytest.raises(ConfigError, match="IMMICH_URL"):
        load_env()


def test_load_env_no_api_key_raises(monkeypatch):
    monkeypatch.setenv("IMMICH_URL", "http://immich:2283/api")
    monkeypatch.delenv("IMMICH_API_KEY", raising=False)
    monkeypatch.delenv("IMMICH_API_KEY_FILE", raising=False)
    with pytest.raises(ConfigError, match="IMMICH_API_KEY"):
        load_env()


def test_load_env_both_api_keys_raises(monkeypatch):
    monkeypatch.setenv("IMMICH_URL", "http://immich:2283/api")
    monkeypatch.setenv("IMMICH_API_KEY", "key")
    monkeypatch.setenv("IMMICH_API_KEY_FILE", "/path/to/key")
    with pytest.raises(ConfigError, match="IMMICH_API_KEY"):
        load_env()


def test_load_env_api_key_from_env(monkeypatch):
    monkeypatch.setenv("IMMICH_URL", "http://immich:2283/api")
    monkeypatch.setenv("IMMICH_API_KEY", "mykey")
    monkeypatch.delenv("IMMICH_API_KEY_FILE", raising=False)
    env = load_env()
    assert env.api_key == "mykey"
    assert env.immich_url == "http://immich:2283/api"


def test_load_env_api_key_from_file(tmp_path, monkeypatch):
    key_file = tmp_path / "api_key"
    key_file.write_text("filekey\n")
    monkeypatch.setenv("IMMICH_URL", "http://immich:2283/api")
    monkeypatch.delenv("IMMICH_API_KEY", raising=False)
    monkeypatch.setenv("IMMICH_API_KEY_FILE", str(key_file))
    env = load_env()
    assert env.api_key == "filekey"


def test_load_env_apply_default_false(monkeypatch):
    monkeypatch.setenv("IMMICH_URL", "http://immich:2283/api")
    monkeypatch.setenv("IMMICH_API_KEY", "key")
    monkeypatch.delenv("APPLY", raising=False)
    env = load_env()
    assert env.apply is False


def test_load_env_apply_one_sets_true(monkeypatch):
    monkeypatch.setenv("IMMICH_URL", "http://immich:2283/api")
    monkeypatch.setenv("IMMICH_API_KEY", "key")
    monkeypatch.setenv("APPLY", "1")
    env = load_env()
    assert env.apply is True
