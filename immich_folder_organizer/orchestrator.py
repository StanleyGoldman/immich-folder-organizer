import logging
import sys

from .config import load_config, load_env, ConfigError
from .immich_client import ImmichClient
from .executor import Executor
from .reconciler import reconcile, reconcile_properties

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def main():
    try:
        env = load_env()
    except ConfigError as e:
        log.error("Configuration error: %s", e)
        sys.exit(1)

    try:
        config = load_config(env.config_file)
    except (ConfigError, FileNotFoundError, Exception) as e:
        log.error("Failed to load config: %s", e)
        sys.exit(1)

    client = ImmichClient(env.immich_url, env.api_key)
    executor = Executor(client, env.apply)

    if not env.apply:
        log.info("DRY RUN — no changes will be made (set APPLY=1 to commit)")

    all_assets = client.get_all_assets()

    for album_cfg in config.albums:
        album_id = executor.ensure_album(album_cfg.name, album_cfg.description or "")
        if album_id is None:
            # dry-run: no album id; preview asset and property plans
            asset_plan = reconcile(album_cfg, [], all_assets)
            executor.sync_assets(None, album_cfg.name, asset_plan)
            prop_plan = reconcile_properties(album_cfg, None, [])
            executor.sync_properties(None, album_cfg.name, prop_plan)
            continue

        album_info = client.get_album_info(album_id)
        current_ids = [a.id for a in album_info.assets]
        asset_plan = reconcile(album_cfg, current_ids, all_assets)
        executor.sync_assets(album_id, album_cfg.name, asset_plan)

        # After sync, the album's asset list is the newly reconciled set
        album_assets = [a for a in all_assets if a.id in set(current_ids) - set(asset_plan.to_remove)]
        album_assets += [a for a in all_assets if a.id in set(asset_plan.to_add)]

        prop_plan = reconcile_properties(album_cfg, album_info, album_assets)
        executor.sync_properties(album_id, album_cfg.name, prop_plan)

    if config.delete_orphaned_albums:
        _delete_orphaned_albums(client, executor, config)


def _delete_orphaned_albums(client, executor, config):
    from .marker import has_marker

    declared_names = {alb.name for alb in config.albums}
    all_albums = client.get_all_albums()

    for album in all_albums:
        if album.album_name in declared_names:
            continue
        if not has_marker(album.description or ""):
            continue
        executor.delete_orphaned_album(album.id, album.album_name)
