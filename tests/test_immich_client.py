"""ImmichClient against a fake Immich v3 HTTP server.

The real immichpy client and models are exercised end to end; only the
server is fake. Response bodies follow the Immich v3.3.5 API shape.
"""
import asyncio
import threading
import uuid

import pytest
from aiohttp import web

from immich_folder_organizer.immich_client import ImmichClient

OWNER_ID = "0b1c2d3e-0000-4000-8000-000000000001"
ALBUM_ID = "b0000000-0000-4000-8000-000000000001"
ASSET_1 = "a0000000-0000-4000-8000-000000000001"
ASSET_2 = "a0000000-0000-4000-8000-000000000002"
USER_ID = "c0000000-0000-4000-8000-000000000001"


def _asset(asset_id, path):
    return {
        "id": asset_id,
        "checksum": "c2hhMQ==",
        "createdAt": "2024-01-01T00:00:00.000Z",
        "deviceAssetId": None,
        "deviceId": None,
        "duration": 0,
        "fileCreatedAt": "2024-01-01T00:00:00.000Z",
        "fileModifiedAt": "2024-01-01T00:00:00.000Z",
        "hasMetadata": True,
        "height": 100,
        "isArchived": False,
        "isEdited": False,
        "isFavorite": False,
        "isOffline": False,
        "isTrashed": False,
        "libraryId": None,
        "livePhotoVideoId": None,
        "localDateTime": "2024-01-01T00:00:00.000Z",
        "originalFileName": path.rsplit("/", 1)[-1],
        "originalMimeType": "image/jpeg",
        "originalPath": path,
        "ownerId": OWNER_ID,
        "thumbhash": None,
        "type": "IMAGE",
        "updatedAt": "2024-01-01T00:00:00.000Z",
        "visibility": "timeline",
        "width": 100,
    }


def _search_response(items, next_page=None):
    return {
        "albums": {"count": 0, "facets": [], "items": [], "total": 0},
        "assets": {
            "count": len(items),
            "facets": [],
            "items": items,
            "nextCursor": None,
            "nextPage": next_page,
            "total": len(items),
        },
    }


def _album(album_id, name):
    return {
        "id": album_id,
        "albumName": name,
        "albumThumbnailAssetId": None,
        # v3 lists the owner among the album users
        "albumUsers": [{
            "role": "owner",
            "user": {
                "avatarColor": "primary",
                "email": "owner@example.com",
                "id": OWNER_ID,
                "name": "Owner",
                "profileChangedAt": "2024-01-01T00:00:00.000Z",
                "profileImagePath": "",
            },
        }],
        "assetCount": 0,
        "createdAt": "2024-01-01T00:00:00.000Z",
        "description": "",
        "hasSharedLink": False,
        "isActivityEnabled": True,
        "order": "desc",
        "shared": False,
        "updatedAt": "2024-01-01T00:00:00.000Z",
    }


class FakeImmich:
    """A minimal Immich server on a background thread.

    `routes` maps (method, path) to a function taking the parsed JSON body
    (or None) and returning the JSON response body. Every request is recorded
    in `requests` as (method, path, query, body).
    """

    def __init__(self):
        self.routes = {}
        self.requests = []
        self._loop = asyncio.new_event_loop()
        self._runner = None
        self.base_url = None

    def route(self, method, path, handler):
        self.routes[(method, path)] = handler

    async def _handle(self, request):
        body = await request.json() if request.can_read_body else None
        self.requests.append((request.method, request.path, dict(request.query), body))
        handler = self.routes.get((request.method, request.path))
        if handler is None:
            return web.json_response({"message": "Not found"}, status=404)
        result = handler(body)
        if result is None:
            return web.Response(status=204)
        return web.json_response(result)

    async def _start(self):
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self._handle)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await site.start()
        port = self._runner.addresses[0][1]
        self.base_url = f"http://127.0.0.1:{port}/api"

    def start(self):
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        asyncio.run_coroutine_threadsafe(self._start(), self._loop).result()

    def stop(self):
        asyncio.run_coroutine_threadsafe(self._runner.cleanup(), self._loop).result()
        self._loop.call_soon_threadsafe(self._loop.stop)

    def requests_to(self, method, path):
        return [r for r in self.requests if r[0] == method and r[1] == path]


@pytest.fixture
def server():
    fake = FakeImmich()
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture
def client(server):
    return ImmichClient(server.base_url, "test-key")


def test_get_all_assets_parses_v3_search_response(server, client):
    server.route(
        "POST", "/api/search/metadata",
        lambda body: _search_response([_asset(ASSET_1, "/photos/a.jpg")]),
    )

    assets = client.get_all_assets()

    assert [str(a.id) for a in assets] == [ASSET_1]
    assert assets[0].original_path == "/photos/a.jpg"


def test_get_all_assets_follows_next_page_across_pages(server, client):
    pages = {
        1: _search_response([_asset(ASSET_1, "/photos/a.jpg")], next_page="2"),
        2: _search_response([_asset(ASSET_2, "/photos/b.jpg")]),
    }
    server.route("POST", "/api/search/metadata", lambda body: pages[body["page"]])

    assets = client.get_all_assets()

    assert [str(a.id) for a in assets] == [ASSET_1, ASSET_2]


def test_get_all_assets_requests_timeline_visibility(server, client):
    # v3 widened the search default from timeline to every non-locked
    # visibility; v2 behavior (timeline only) is kept by asking for it.
    server.route("POST", "/api/search/metadata", lambda body: _search_response([]))

    client.get_all_assets()

    [(_, _, _, body)] = server.requests_to("POST", "/api/search/metadata")
    assert body["visibility"] == "timeline"


def test_get_album_asset_ids_lists_timeline_and_archived_album_assets(server, client):
    # v3 dropped `assets` from the album response; album contents come from
    # search instead, matching v2's album view (timeline + archive).
    by_visibility = {
        "timeline": [_asset(ASSET_1, "/photos/a.jpg")],
        "archive": [_asset(ASSET_2, "/photos/b.jpg")],
    }
    server.route(
        "POST", "/api/search/metadata",
        lambda body: _search_response(by_visibility[body["visibility"]]),
    )

    ids = client.get_album_asset_ids(ALBUM_ID)

    assert sorted(str(i) for i in ids) == [
        ASSET_1,
        ASSET_2,
    ]
    bodies = [r[3] for r in server.requests_to("POST", "/api/search/metadata")]
    assert all(b["albumIds"] == [ALBUM_ID] for b in bodies)



def test_get_all_albums_excludes_albums_shared_with_the_user(server, client):
    # v3 also returns albums other users shared with us unless told not to;
    # v2 returned only the API user's own albums.
    server.route("GET", "/api/albums", lambda body: [_album(ALBUM_ID, "Italy")])

    albums = client.get_all_albums()

    assert [a.album_name for a in albums] == ["Italy"]
    [(_, _, query, _)] = server.requests_to("GET", "/api/albums")
    assert query == {"isOwned": "true"}


def test_revoke_share_accepts_uuid_user_id_from_v3_models(server, client):
    user_id = uuid.UUID(USER_ID)
    path = f"/api/albums/{ALBUM_ID}/user/{user_id}"
    server.route("DELETE", path, lambda body: None)

    client.revoke_share(ALBUM_ID, user_id)

    assert len(server.requests_to("DELETE", path)) == 1


def test_album_writes_accept_str_and_uuid_ids(server, client):
    # immichpy 9.x types these parameters as UUID; callers pass str album
    # IDs and the UUID asset/user IDs that v3 models return.
    asset_id = uuid.UUID(ASSET_1)
    user_id = uuid.UUID(USER_ID)
    album_path = f"/api/albums/{ALBUM_ID}"
    bulk_result = [{"id": str(asset_id), "success": True}]
    server.route("PUT", f"{album_path}/assets", lambda body: bulk_result)
    server.route("DELETE", f"{album_path}/assets", lambda body: bulk_result)
    server.route("PATCH", album_path, lambda body: _album(ALBUM_ID, "Italy"))
    server.route("PUT", f"{album_path}/users", lambda body: _album(ALBUM_ID, "Italy"))
    server.route("DELETE", album_path, lambda body: None)

    client.add_assets(ALBUM_ID, [asset_id])
    client.remove_assets(ALBUM_ID, [asset_id])
    client.update_album(ALBUM_ID, thumbnail_asset_id=asset_id, sort_order="asc")
    client.share_album(ALBUM_ID, user_id, "viewer")
    client.delete_album(ALBUM_ID)

    bodies = {(m, p): b for m, p, _, b in server.requests}
    assert bodies[("PUT", f"{album_path}/assets")] == {"ids": [str(asset_id)]}
    assert bodies[("DELETE", f"{album_path}/assets")] == {"ids": [str(asset_id)]}
    assert bodies[("PATCH", album_path)] == {
        "albumThumbnailAssetId": str(asset_id),
        "order": "asc",
    }
    assert bodies[("PUT", f"{album_path}/users")] == {
        "albumUsers": [{"role": "viewer", "userId": str(user_id)}],
    }
    assert ("DELETE", album_path) in bodies
