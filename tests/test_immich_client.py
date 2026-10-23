"""ImmichClient against a fake Immich v3 HTTP server.

The real immichpy client and models are exercised end to end; only the
server is fake.
"""
import uuid

from tests.fake_immich import album, asset, search_response

ALBUM_ID = "b0000000-0000-4000-8000-000000000001"
ASSET_1 = "a0000000-0000-4000-8000-000000000001"
ASSET_2 = "a0000000-0000-4000-8000-000000000002"
USER_ID = "c0000000-0000-4000-8000-000000000001"


def test_get_all_assets_parses_v3_search_response(server, client):
    server.route(
        "POST", "/api/search/metadata",
        lambda body: search_response([asset(ASSET_1, "/photos/a.jpg")]),
    )

    assets = client.get_all_assets()

    assert [str(a.id) for a in assets] == [ASSET_1]
    assert assets[0].original_path == "/photos/a.jpg"


def test_get_all_assets_follows_next_page_across_pages(server, client):
    pages = {
        1: search_response([asset(ASSET_1, "/photos/a.jpg")], next_page="2"),
        2: search_response([asset(ASSET_2, "/photos/b.jpg")]),
    }
    server.route("POST", "/api/search/metadata", lambda body: pages[body["page"]])

    assets = client.get_all_assets()

    assert [str(a.id) for a in assets] == [ASSET_1, ASSET_2]


def test_get_all_assets_requests_timeline_visibility(server, client):
    # v3 widened the search default from timeline to every non-locked
    # visibility; v2 behavior (timeline only) is kept by asking for it.
    server.route("POST", "/api/search/metadata", lambda body: search_response([]))

    client.get_all_assets()

    [(_, _, _, body)] = server.requests_to("POST", "/api/search/metadata")
    assert body["visibility"] == "timeline"


def test_get_album_asset_ids_lists_timeline_and_archived_album_assets(server, client):
    # v3 dropped `assets` from the album response; album contents come from
    # search instead, matching v2's album view (timeline + archive).
    by_visibility = {
        "timeline": [asset(ASSET_1, "/photos/a.jpg")],
        "archive": [asset(ASSET_2, "/photos/b.jpg")],
    }
    server.route(
        "POST", "/api/search/metadata",
        lambda body: search_response(by_visibility[body["visibility"]]),
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
    server.route("GET", "/api/albums", lambda body: [album(ALBUM_ID, "Italy")])

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
    server.route("PATCH", album_path, lambda body: album(ALBUM_ID, "Italy"))
    server.route("PUT", f"{album_path}/users", lambda body: album(ALBUM_ID, "Italy"))
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
