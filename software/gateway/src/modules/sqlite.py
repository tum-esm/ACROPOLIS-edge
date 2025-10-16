import os
import sqlite3
from enum import Enum
from typing import Any
from threading import Lock


from utils.misc import fatal_error
from modules.logging import info


class SqliteTables(Enum):
    CONTROLLER_MESSAGES = "messages"
    HEALTH_CHECK = "health_check"
    PENDING_MQTT_MESSAGES = "pending_mqtt_messages"


class SqliteConnection:
    def __init__(self, path : str, nr_retries : int = 3, dont_retry : bool = False) -> None:
        self.path = path
        self.db_unavailable = True
        self.write_lock = Lock()
        try:
            self.conn = sqlite3.connect(path, cached_statements=0, isolation_level=None, autocommit=True, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL;")       # enable write-ahead logging
            self.conn.execute("PRAGMA busy_timeout = 5000;")    # 5 seconds timeout for when the db is locked
            self.conn.execute("PRAGMA auto_vacuum  = FULL;")    # shrink the db file size when possible
            self.db_unavailable = False
        except Exception as e:
            if dont_retry:
                print(f'[SQLITE][FATAL][NO_RETRY] Failed to connect to sqlite db at "{self.path}": {e}')
                return
            if nr_retries <= 0:
                fatal_error(
                    f'[SQLITE][FATAL] Failed to connect to sqlite db at "{self.path}": {e}'
                )
            self.reset_db_conn(e, nr_retries - 1)

    def does_table_exist(self, table) -> bool:
        return len(
            self.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )) > 0

    def is_table_empty(self, table) -> bool:
        return self.execute(f"SELECT COUNT(*) FROM {table}")[0][0] == 0

    def do_table_values_exist(self, table):
        return self.does_table_exist(table) and not self.is_table_empty(table)

    def check(self) -> None:
        return self.execute(
            "SELECT name FROM sqlite_master WHERE type='table';")

    def execute(self, query, params=()) -> Any:
        if self.db_unavailable:
            return None
        with self.write_lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(query, params)
                fetch = cursor.fetchall()
            except Exception as e:
                if "no such table" in str(e):
                    return [()]
                self.reset_db_conn(e)
                return self.execute(query)
            return fetch

    def close(self) -> None:
        self.conn.close()

    def reset_db_conn(self, error_msg, nr_retries=3) -> None:
        self.db_unavailable = True
        info(f"[SQLITE]: SQLite error at '{self.path}': {str(error_msg)}")
        info(f"[SQLITE]: resetting sqlite db at '{self.path}'")
        try:
            self.close()
            os.remove(self.path)
        except Exception as e:
            fatal_error(f'Failed to reset sqlite db at "{self.path}": {e}')

        try:
            self.__init__(self.path, nr_retries - 1)  # type: ignore[misc]
        except Exception as e:
            fatal_error(f'Failed to reset sqlite db at "{self.path}": {e}')
