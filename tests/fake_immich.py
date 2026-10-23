"""A fake Immich v3 server for tests, and builders for its JSON bodies.

Bodies follow the Immich v3.3.5 API shape, so the real immichpy models
parse them. Use the `server` and `client` fixtures from conftest.py.
"""

import asyncio
import threading

from aiohttp import web

OWNER_ID = "0b1c2d3e-0000-4000-8000-000000000001"


def asset(asset_id, path, visibility="timeline"):
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
        "visibility": visibility,
        "width": 100,
    }


def search_response(items, next_page=None):
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


def user(user_id, name):
    return {
        "avatarColor": "primary",
        "email": f"{name}@example.com",
        "id": user_id,
        "name": name,
        "profileChangedAt": "2024-01-01T00:00:00.000Z",
        "profileImagePath": "",
    }


def album(album_id, name, description="", shared_with=()):
    """`shared_with` is (user, role) pairs listed after the owner."""
    return {
        "id": album_id,
        "albumName": name,
        "albumThumbnailAssetId": None,
        # v3 lists the owner among the album users
        "albumUsers": [{"role": "owner", "user": user(OWNER_ID, "owner")}]
        + [{"role": role, "user": u} for u, role in shared_with],
        "assetCount": 0,
        "createdAt": "2024-01-01T00:00:00.000Z",
        "description": description,
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
