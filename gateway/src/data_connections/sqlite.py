import sqlite3
from enum import Enum

class SqliteTables(Enum):
    MESSAGES = "messages"
    STATE = "state"


class SqliteConnection:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)

    def is_empty(self, table):
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