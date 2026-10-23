"""Full runs of the orchestrator against a fake Immich v3 server.

These catch API-shape breaks that unit tests with mocked clients miss,
like v3 dropping `assets` from album responses.
"""
import textwrap

import pytest

from immich_folder_organizer import orchestrator
from immich_folder_organizer.marker import with_marker
from tests.fake_immich import album, asset, search_response, user

ALBUM_ID = "b0000000-0000-4000-8000-000000000001"
ORPHAN_ID = "b0000000-0000-4000-8000-000000000002"
KEPT = "a0000000-0000-4000-8000-000000000001"
NEW = "a0000000-0000-4000-8000-000000000002"
STALE = "a0000000-0000-4000-8000-000000000003"
ALICE = "c0000000-0000-4000-8000-000000000001"
BOB = "c0000000-0000-4000-8000-000000000002"

CONFIG = """
    albums:
      - name: Italy
        description: Trip
        paths: [/photos/italy]
        thumbnail: first
        sort_order: asc
        share_with:
          - user: alice
            role: editor
"""


@pytest.fixture
def immich(server):
    """A library with one tool-managed album, "Italy".

    The album holds KEPT (timeline) and STALE (archived, outside its
    source paths), and is shared with bob. NEW is under the source paths
    but not yet in the album.
    """
    bob = user(BOB, "bob")
    italy = album(ALBUM_ID, "Italy", with_marker("Trip"), shared_with=[(bob, "viewer")])
    album_contents = {
        "timeline": [asset(KEPT, "/photos/italy/a.jpg")],
        "archive": [asset(STALE, "/photos/other/c.jpg", visibility="archive")],
    }
    library = [
        asset(KEPT, "/photos/italy/a.jpg"),
        asset(NEW, "/photos/italy/b.jpg"),
        asset(STALE, "/photos/other/c.jpg"),
    ]

    def search(body):
        if body.get("albumIds"):
            return search_response(album_contents[body["visibility"]])
        return search_response(library)

    album_path = f"/api/albums/{ALBUM_ID}"
    bulk_result = [{"id": NEW, "success": True}]
    server.route("GET", "/api/albums", lambda body: [italy])
    server.route("GET", album_path, lambda body: italy)
    server.route("POST", "/api/search/metadata", search)
    server.route("GET", "/api/users", lambda body: [user(ALICE, "alice"), bob])
    server.route("PUT", f"{album_path}/assets", lambda body: bulk_result)
    server.route("DELETE", f"{album_path}/assets", lambda body: bulk_result)
    server.route("PATCH", album_path, lambda body: italy)
    server.route("PUT", f"{album_path}/users", lambda body: italy)
    server.route("DELETE", f"{album_path}/user/{BOB}", lambda body: None)
    return server


def _run(server, monkeypatch, tmp_path, config, apply):
    config_file = tmp_path / "albums.yaml"
    config_file.write_text(textwrap.dedent(config))
    monkeypatch.setenv("IMMICH_URL", server.base_url)
    monkeypatch.setenv("IMMICH_API_KEY", "test-key")
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("APPLY", "1" if apply else "")
    orchestrator.main()


def _writes(server):
    return [
        (method, path, body)
        for method, path, _, body in server.requests
        if method != "GET" and path != "/api/search/metadata"
    ]


def test_apply_reconciles_assets_properties_and_shares(immich, monkeypatch, tmp_path):
    _run(immich, monkeypatch, tmp_path, CONFIG, apply=True)

    album_path = f"/api/albums/{ALBUM_ID}"
    assert _writes(immich) == [
        ("PUT", f"{album_path}/assets", {"ids": [NEW]}),
        ("DELETE", f"{album_path}/assets", {"ids": [STALE]}),
        ("PATCH", album_path, {
            "albumThumbnailAssetId": KEPT,
            "description": with_marker("Trip"),
            "order": "asc",
        }),
        ("PUT", f"{album_path}/users", {"albumUsers": [{"role": "editor", "userId": ALICE}]}),
        ("DELETE", f"{album_path}/user/{BOB}", None),
    ]


def test_dry_run_sends_no_writes(immich, monkeypatch, tmp_path):
    _run(immich, monkeypatch, tmp_path, CONFIG, apply=False)

    assert _writes(immich) == []


def test_orphaned_album_is_deleted_when_enabled(immich, monkeypatch, tmp_path):
    orphan = album(ORPHAN_ID, "Old trip", with_marker(""))
    italy = immich.routes[("GET", f"/api/albums/{ALBUM_ID}")](None)
    immich.route("GET", "/api/albums", lambda body: [italy, orphan])
    immich.route("DELETE", f"/api/albums/{ORPHAN_ID}", lambda body: None)

    config = "\n    delete_orphaned_albums: true" + CONFIG
    _run(immich, monkeypatch, tmp_path, config, apply=True)

    writes = _writes(immich)
    assert ("DELETE", f"/api/albums/{ORPHAN_ID}", None) in writes
    assert ("DELETE", f"/api/albums/{ALBUM_ID}", None) not in writes
