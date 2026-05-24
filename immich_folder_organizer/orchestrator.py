import logging
import sys

from .config import load_config, load_env, ConfigError
from .immich_client import ImmichClient
from .executor import Executor
from .reconciler import reconcile

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
        album_id = executor.ensure_album(album_cfg.name)
        if album_id is None:
            # dry-run: no album id to work with
            plan = reconcile(album_cfg, [], all_assets)
            executor.sync_assets(None, album_cfg.name, plan)
            continue

        album_info = client.get_album_info(album_id)
        current_ids = [a.id for a in album_info.assets]
        plan = reconcile(album_cfg, current_ids, all_assets)
        executor.sync_assets(album_id, album_cfg.name, plan)
