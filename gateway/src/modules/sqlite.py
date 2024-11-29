import sqlite3
from enum import Enum

class SqliteTables(Enum):
    QUEUE_OUT = "queue_out"
    STATE = "state"


class SqliteConnection:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, cached_statements=0, isolation_level=None, autocommit=True)
        self.conn.execute("PRAGMA journal_mode=WAL;")       # enable write-ahead logging
        self.conn.execute("PRAGMA busy_timeout = 5000;")    # 5 seconds timeout for when the db is locked

    def does_table_exist(self, table):
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        return cursor.fetchone() is not None

    def is_table_empty(self, table):
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0] == 0

    def check(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        return cursor.fetchall()

    def execute(self, query):
        cursor = self.conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()

    def close(self):
        self.conn.close()