import json
from typing import Final

from config import (
    ENABLE_SCHEDULED_UPDATE_TGDB_DATABASE,
    SCHEDULED_UPDATE_TGDB_DATABASE_CRON,
)
from tasks.tasks import RemoteFilePullTask
from logger.logger import log
from handler.redis_handler import cache

TGDB_GAMES_DATABASE_KEY: Final = "romm:tgdb_index"
TGDB_BOXARTS_DATABASE_KEY: Final = "romm:tgdb_boxart"
TGDB_DATABASE_LAST_EDIT_KEY: Final = "romm:tgdb_database_last_edit"

class UpdateTGDBDatabaseTask(RemoteFilePullTask):
    def __init__(self):
        super().__init__(
            func="tasks.update_tgdb_database.update_tgdb_database_task.run",
            description="TGDB database update",
            enabled=ENABLE_SCHEDULED_UPDATE_TGDB_DATABASE,
            cron_string=SCHEDULED_UPDATE_TGDB_DATABASE_CRON,
            url="https://cdn.thegamesdb.net/json/database-latest.json",
        )

    async def run(self, force: bool = False):
        content = await super().run(force)
        if content is None:
            return

        database_json = json.loads(content)
        if database_json['code'] != 200:
            log.error("Failed to fetch TGDB database: (%s) %s", database_json['code'], database_json['status'])
            return

        last_edit_id = database_json["last_edit_id"]
        last_edit_id_cache = cache.get(TGDB_DATABASE_LAST_EDIT_KEY)
        if not last_edit_id_cache or last_edit_id == last_edit_id_cache:
            log.info("TGDB database is up to date.")
            return
    
        for game in database_json['data']['games']:
            cache.hset(TGDB_GAMES_DATABASE_KEY, game['id'], json.dumps(game))

        for key, value in database_json['include']['boxart'].items():
            if key and value:
                cache.hset(TGDB_BOXARTS_DATABASE_KEY, key, json.dumps(value))

        cache.set(TGDB_DATABASE_LAST_EDIT_KEY, last_edit_id)
        log.info("Scheduled TGDB database update completed!")


update_tgdb_database_task = UpdateTGDBDatabaseTask()
