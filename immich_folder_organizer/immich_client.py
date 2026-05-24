import asyncio
import math
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
        assets = []
        page = 1
        while True:
            dto = MetadataSearchDto(page=page, size=_PAGE_SIZE)
            result = self._run(lambda c, d=dto: c.search.search_assets(metadata_search_dto=d))
            assets.extend(result.assets.items)
            total_pages = math.ceil(result.assets.total / _PAGE_SIZE)
            if page >= total_pages or result.assets.total == 0:
                break
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
