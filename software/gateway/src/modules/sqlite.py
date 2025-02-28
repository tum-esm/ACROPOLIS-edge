import os
import sqlite3
from enum import Enum
from typing import Any

from modules.mqtt import GatewayMqttClient
from utils.misc import fatal_error


class SqliteTables(Enum):
    QUEUE_OUT = "queue_out"
    STATE = "state"


class SqliteConnection:
    def __init__(self, path : str, nr_retries : int = 3):
        self.path = path
        try:
            self.conn = sqlite3.connect(path, cached_statements=0, isolation_level=None, autocommit=True)
            self.conn.execute("PRAGMA journal_mode=WAL;")       # enable write-ahead logging
            self.conn.execute("PRAGMA busy_timeout = 5000;")    # 5 seconds timeout for when the db is locked
        except Exception as e:
            if nr_retries <= 0:
                fatal_error(f'[SQLITE][FATAL] Failed to connect to sqlite db at "{self.path}": {e}')
            self.reset_db_conn(e, nr_retries - 1)

    def does_table_exist(self, table) -> bool:
        return len(self.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")) > 0

    def is_table_empty(self, table) -> bool:
        return self.execute(f"SELECT COUNT(*) FROM {table}")[0][0] == 0

    def check(self) -> None:
        return self.execute("SELECT name FROM sqlite_master WHERE type='table';")

    def execute(self, query) -> Any:
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            fetch = cursor.fetchall()
        except Exception as e:
            self.reset_db_conn(e)
            return self.execute(query)
        return fetch

    def close(self) -> None:
        self.conn.close()

    def reset_db_conn(self, error_msg, nr_retries=3) -> None:
        GatewayMqttClient().publish_log('WARN', f'WARNING: SQLite error at "{self.path}": {str(error_msg)}')
        GatewayMqttClient().publish_log('WARN', f'WARNING: resetting sqlite db at "{self.path}"')
        try:
            self.close()
            os.remove(self.path)
        except Exception as e:
            fatal_error(f'Failed to reset sqlite db at "{self.path}": {e}')

        try:
            self.__init__(self.path, nr_retries - 1)  # type: ignore[misc]
        except Exception as e:
            fatal_error(f'Failed to reset sqlite db at "{self.path}": {e}')