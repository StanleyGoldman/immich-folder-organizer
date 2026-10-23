# Immich API assumptions

`ImmichClient` is the only module that talks to Immich, through the `immichpy` client pinned in `pyproject.toml` (locked in `uv.lock`). Its correctness rests on server behavior that the generated models do not show: defaults, filters, and what each response includes. This page lists that behavior as of Immich v3.3.5, so an upgrade can be checked item by item.

## Endpoints and the behavior relied on

| Client method | Endpoint | Behavior relied on |
|---|---|---|
| `get_all_assets` | `POST /search/metadata` | Sends `visibility=timeline`. With no `visibility`, v3 returns every non-locked asset (archive and hidden included); v2 defaulted to timeline. |
| `get_all_assets`, `get_album_asset_ids` | `POST /search/metadata` | Paged with `page`/`size`, following `nextPage`. v3 fills `nextPage` only for requests without `filter`, `orderBy` or `cursor`; those switch to `nextCursor`. `page` and the flat filters (`albumIds`, `visibility`) are deprecated since v3.2 but still served. |
| `get_album_asset_ids` | `POST /search/metadata` with `albumIds` | Album responses carry no assets in v3, so album contents come from search, once for `timeline` and once for `archive`, matching v2's album view. Searching with `albumIds` drops the per-user filter, so assets other users added to the album are included. |
| `get_all_albums` | `GET /albums?isOwned=true` | Without `isOwned`, v3 also returns albums other users shared with the API user. |
| `get_album_info` | `GET /albums/:id` | `albumUsers` lists the owner with role `owner`. `reconcile_shares` ignores that entry. |
| `revoke_share` | `DELETE /albums/:id/user/:userId` | immichpy types `user_id` as a strict `str` while its models return `UUID`s; the client converts. |
| `add_assets`, `remove_assets`, `update_album`, `share_album`, `delete_album`, `create_album` | `PUT`/`DELETE /albums/:id/assets`, `PATCH`/`DELETE /albums/:id`, `PUT /albums/:id/users`, `POST /albums` | Plain writes. IDs are `UUID`s from immichpy models. |
| `get_all_users` | `GET /users` | Users are matched to `share_with` entries by `name` or `email`. |

## Checking an upgrade

1. Read the release's migration guide (for v3: <https://immich.app/blog/v3-migration>) and mark each item as affecting the organizer or not.
2. For each row above, compare the server source at the current and target release tags. The service layer holds the defaults:
   ```sh
   gh api "repos/immich-app/immich/contents/server/src/services/search.service.ts?ref=v3.3.5" \
     -H "Accept: application/vnd.github.raw"
   ```
   Also `album.service.ts`, `server/src/repositories/search.repository.ts`, `server/src/repositories/album.repository.ts`, `server/src/utils/database.ts` and `server/src/dtos/search.dto.ts`.
3. Run `make ci`. `tests/test_orchestrator.py` runs a full reconciliation against `tests/fake_immich.py`. Update the fake's JSON to the new API shape first, so the tests exercise the new models.
4. Update this page.
