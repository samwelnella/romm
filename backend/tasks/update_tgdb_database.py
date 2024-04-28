import json
from typing import Final

from config import (
    ENABLE_SCHEDULED_UPDATE_TGDB_METADATA,
    SCHEDULED_UPDATE_TGDB_METADATA_CRON,
)
from tasks.tasks import RemoteFilePullTask
from logger.logger import log
from handler.redis_handler import cache

TGDB_INDEX_KEY: Final = "romm:tgdb_index"
