import os
from dataclasses import dataclass, field
from typing import Optional
import yaml


class ConfigError(ValueError):
    pass


@dataclass
class ShareEntry:
    user: str
    role: str = "viewer"


@dataclass
class AlbumConfig:
    name: str
    paths: list
    exclude: list = field(default_factory=list)
    description: Optional[str] = None
    sort_order: Optional[str] = None
    thumbnail: Optional[str] = None
    comments_and_likes: Optional[bool] = None
    share_with: Optional[list] = None


@dataclass
class Config:
    albums: list
    delete_orphaned_albums: bool = False


@dataclass
class Env:
    immich_url: str
    api_key: str
    apply: bool
    config_file: str


def load_config(path: str) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)

    raw_albums = data.get("albums", [])
    albums = []
    for i, entry in enumerate(raw_albums):
        if "name" not in entry:
            raise ConfigError(f"Album entry {i} is missing required field 'name'")
        if "paths" not in entry:
            raise ConfigError(f"Album '{entry.get('name', i)}' is missing required field 'paths'")

        share_with = None
        if "share_with" in entry:
            share_with = [
                ShareEntry(user=s["user"], role=s.get("role", "viewer"))
                for s in entry["share_with"]
            ]

        albums.append(
            AlbumConfig(
                name=entry["name"],
                paths=entry["paths"],
                exclude=entry.get("exclude", []),
                description=entry.get("description"),
                sort_order=entry.get("sort_order"),
                thumbnail=entry.get("thumbnail"),
                comments_and_likes=entry.get("comments_and_likes"),
                share_with=share_with,
            )
        )

    return Config(
        albums=albums,
        delete_orphaned_albums=data.get("delete_orphaned_albums", False),
    )


def load_env() -> Env:
    url = os.environ.get("IMMICH_URL")
    if not url:
        raise ConfigError("IMMICH_URL environment variable is required")

    api_key_val = os.environ.get("IMMICH_API_KEY")
    api_key_file = os.environ.get("IMMICH_API_KEY_FILE")

    if api_key_val and api_key_file:
        raise ConfigError(
            "Set exactly one of IMMICH_API_KEY or IMMICH_API_KEY_FILE, not both"
        )
    if not api_key_val and not api_key_file:
        raise ConfigError(
            "One of IMMICH_API_KEY or IMMICH_API_KEY_FILE is required"
        )

    if api_key_file:
        with open(api_key_file) as f:
            api_key = f.read().strip()
    else:
        api_key = api_key_val

    apply = os.environ.get("APPLY", "") == "1"
    config_file = os.environ.get("CONFIG_FILE", "/config/albums.yaml")

    return Env(
        immich_url=url,
        api_key=api_key,
        apply=apply,
        config_file=config_file,
    )
