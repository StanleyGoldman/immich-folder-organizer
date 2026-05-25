import asyncio
import logging
from typing import Optional

from immichpy import AsyncClient
from immichpy.client.generated.models import (
    AlbumResponseDto,
    AssetResponseDto,
    BulkIdsDto,
    CreateAlbumDto,
    AlbumUserAddDto,
    AddUsersDto,
    AlbumUserRole,
    AssetOrder,
    UpdateAlbumDto,
)
from immichpy.client.generated.models.metadata_search_dto import MetadataSearchDto

_PAGE_SIZE = 1000

log = logging.getLogger(__name__)


class ImmichClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._api_key = api_key

    def _run(self, coro_fn):
        async def _call():
            async with AsyncClient(api_key=self._api_key, base_url=self._base_url) as client:
                return await coro_fn(client)

        return asyncio.run(_call())

    def get_all_albums(self) -> list:
        return self._run(lambda c: c.albums.get_all_albums())

    def get_album_info(self, album_id: str) -> AlbumResponseDto:
        return self._run(lambda c: c.albums.get_album_info(id=album_id))

    def get_album_by_name(self, name: str) -> Optional[AlbumResponseDto]:
        albums = self.get_all_albums()
        for album in albums:
            if album.album_name == name:
                return album
        return None

    def create_album(self, name: str, description: str = "") -> AlbumResponseDto:
        return self._run(
            lambda c: c.albums.create_album(
                CreateAlbumDto(album_name=name, description=description)
            )
        )

    def update_album(self, album_id: str, **kwargs) -> AlbumResponseDto:
        dto_kwargs = {}
        if "description" in kwargs:
            dto_kwargs["description"] = kwargs["description"]
        if "sort_order" in kwargs:
            dto_kwargs["order"] = AssetOrder(kwargs["sort_order"])
        if "is_activity_enabled" in kwargs:
            dto_kwargs["is_activity_enabled"] = kwargs["is_activity_enabled"]
        if "thumbnail_asset_id" in kwargs:
            dto_kwargs["album_thumbnail_asset_id"] = kwargs["thumbnail_asset_id"]

        dto = UpdateAlbumDto(**dto_kwargs)
        _id = album_id
        return self._run(lambda c: c.albums.update_album_info(id=_id, update_album_dto=dto))

    def add_assets(self, album_id: str, asset_ids: list) -> None:
        if not asset_ids:
            return
        _id = album_id
        _ids = asset_ids
        self._run(
            lambda c: c.albums.add_assets_to_album(
                id=_id, bulk_ids_dto=BulkIdsDto(ids=_ids)
            )
        )

    def remove_assets(self, album_id: str, asset_ids: list) -> None:
        if not asset_ids:
            return
        _id = album_id
        _ids = asset_ids
        self._run(
            lambda c: c.albums.remove_asset_from_album(
                id=_id, bulk_ids_dto=BulkIdsDto(ids=_ids)
            )
        )

    def delete_album(self, album_id: str) -> None:
        _id = album_id
        self._run(lambda c: c.albums.delete_album(id=_id))

    def get_all_assets(self) -> list:
        """Fetch every asset in the library, paginated.

        Uses the `next_page` cursor from each response as the source of truth
        for pagination. The `total` field in the search response was previously
        used but it returns the count of items in the current batch, not the
        overall match count — so trusting it caused the loop to exit after
        the first page.
        """
        assets = []
        page = 1
        while True:
            dto = MetadataSearchDto(page=page, size=_PAGE_SIZE)
            result = self._run(lambda c, d=dto: c.search.search_assets(metadata_search_dto=d))
            page_items = result.assets.items
            if not page_items:
                break
            assets.extend(page_items)
            log.debug("Fetched assets page %d (%d items, %d total so far)", page, len(page_items), len(assets))

            next_page = result.assets.next_page
            if not next_page:
                break
            try:
                page = int(next_page)
            except (TypeError, ValueError):
                # Unknown cursor format — fall back to incrementing
                page += 1
        return assets

    def get_all_users(self) -> list:
        return self._run(lambda c: c.users.search_users())

    def share_album(self, album_id: str, user_id: str, role: str) -> None:
        _id = album_id
        _user = AlbumUserAddDto(
            user_id=user_id,
            role=AlbumUserRole(role),
        )
        _dto = AddUsersDto(album_users=[_user])
        self._run(
            lambda c: c.albums.add_users_to_album(id=_id, add_users_dto=_dto)
        )

    def revoke_share(self, album_id: str, user_id: str) -> None:
        _id = album_id
        _uid = user_id
        self._run(lambda c: c.albums.remove_user_from_album(id=_id, user_id=_uid))
