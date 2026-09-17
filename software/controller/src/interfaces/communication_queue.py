import os
import sqlite3
from os.path import dirname
import dataclasses
from typing import Union
import time
import json

from custom_types import mqtt_playload_types

PROJECT_DIR = dirname(dirname(os.path.abspath(__file__)))
ACROPOLIS_DATA_PATH = os.environ.get("ACROPOLIS_DATA_PATH") or os.path.join(
    dirname(PROJECT_DIR), "data")

THINGSBOARD_PAYLOADS = Union[mqtt_playload_types.MQTTCO2Data,
                             mqtt_playload_types.MQTTCO2CalibrationData,
                             mqtt_playload_types.MQTTCalibrationCorrectionData,
                             mqtt_playload_types.MQTTSystemData,
                             mqtt_playload_types.MQTTModemInfo,
                             mqtt_playload_types.MQTTWindData,
                             mqtt_playload_types.MQTTWindSensorInfo,
                             mqtt_playload_types.MQTTLogMessage]


class CommunicationQueue:
    """Uses an SQLite database to store messages to be forwarded to the ThingsBoard server by the gateway"""

    def __init__(self) -> None:
        db_path = os.path.join(ACROPOLIS_DATA_PATH, "communication_queue.db")

        self.con = sqlite3.connect(db_path,
                                   isolation_level=None,
                                   autocommit=True)
        # Create queue_out for MQTT messages
        self.con.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type text,
                    message text
                );
            """)
        # Create health_check_queue for health check messages
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS health_check (
                id INTEGER PRIMARY KEY,
                timestamp_ms INTEGER            
            );
        """)
        self.con.execute("PRAGMA journal_mode=WAL;")

    def enqueue_message(self, type: str,
                        payload: THINGSBOARD_PAYLOADS) -> None:
        new_message = {
            "ts": int(time.time_ns() /
                      1_000_000),  # ThingsBoard expects milliseconds
            "values": dataclasses.asdict(payload),
        }
        try:
            with self.con:
                sql_statement: str = "INSERT INTO messages (type, message) VALUES(?, ?);"
                self.con.execute(sql_statement,
                                 (type, json.dumps(new_message)))
                self.con.execute("PRAGMA wal_checkpoint(PASSIVE);")

            time.sleep(1 / 1000)  # sleep for 1ms to avoid duplicate timestamps
        except Exception:
            exit(0)

    def enqueue_health_check(self) -> None:
        ts = int(time.time_ns() / 1_000_000)
        try:
            with self.con:
                sql_statement: str = "INSERT OR REPLACE INTO health_check (id, timestamp_ms) VALUES(?, ?);"
                self.con.execute(sql_statement, (1, ts))
                self.con.execute("PRAGMA wal_checkpoint(PASSIVE);")
        except Exception:
            exit(0)
