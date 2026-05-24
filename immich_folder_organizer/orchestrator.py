import logging
import sys
import time

from .config import load_config, load_env, ConfigError
from .immich_client import ImmichClient
from .executor import Executor
from .reconciler import reconcile, reconcile_properties, reconcile_shares, find_orphaned_albums

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

    t_start = time.monotonic()
    log.info("Starting run: %d album(s) declared in config", len(config.albums))

    all_assets = client.get_all_assets()
    all_users = client.get_all_users()
    log.info("Fetched %d asset(s) and %d user(s) from Immich", len(all_assets), len(all_users))

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

        share_plan = reconcile_shares(album_cfg, album_info.album_users or [], all_users)
        executor.sync_shares(album_id, album_cfg.name, share_plan)

        if _is_noop(asset_plan, prop_plan, share_plan):
            log.info("[ok] '%s' is up to date (%d asset(s))", album_cfg.name, len(current_ids))

    if config.delete_orphaned_albums:
        _delete_orphaned_albums(client, executor, config)

    elapsed = time.monotonic() - t_start
    log.info("Run complete in %.1fs", elapsed)


def _is_noop(asset_plan, prop_plan, share_plan) -> bool:
    no_assets = not asset_plan.to_add and not asset_plan.to_remove
    no_props = (
        prop_plan.description is None
        and prop_plan.sort_order is None
        and prop_plan.is_activity_enabled is None
        and prop_plan.thumbnail_asset_id is None
    )
    no_shares = share_plan.skip or (not share_plan.to_add and not share_plan.to_remove)
    return no_assets and no_props and no_shares


def _delete_orphaned_albums(client, executor, config):
    declared_names = {alb.name for alb in config.albums}
    all_albums = client.get_all_albums()
    orphans = find_orphaned_albums(all_albums, declared_names)
    for album in orphans:
        executor.delete_orphaned_album(album.id, album.album_name)
