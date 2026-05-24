import logging
import sys

from .config import load_config, load_env, ConfigError
from .immich_client import ImmichClient
from .executor import Executor

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

    for album in config.albums:
        executor.ensure_album(album.name)
