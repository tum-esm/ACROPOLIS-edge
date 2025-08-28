import importlib
import os
import time

# get log level from env var
LOG_LEVEL = os.getenv('LOG_LEVEL') or 'INFO'

Sqlite = None
GatewayMqttClient = None
UtilsPaths = None
gateway_logs_buffer_db = None

def log(level: str, message: str):
    print(f'[{level}] {message}')
    if level == 'DEBUG' and LOG_LEVEL != 'DEBUG':
        return

    # import GatewayMqttClient at runtime to avoid circular imports
    global GatewayMqttClient
    if GatewayMqttClient is None:
        GatewayMqttClient = importlib.import_module('modules.mqtt').GatewayMqttClient

    # import UtilsPaths at runtime to avoid circular imports
    global UtilsPaths
    if UtilsPaths is None:
        UtilsPaths = importlib.import_module('utils.paths')

    # import sqlite at runtime to avoid circular imports
    global Sqlite
    if Sqlite is None:
        Sqlite = importlib.import_module('modules.sqlite')

    # initialize gateway_logs_buffer_db if not already initialized
    global gateway_logs_buffer_db
    if gateway_logs_buffer_db is None:
        gateway_logs_buffer_db = Sqlite.SqliteConnection(UtilsPaths.GATEWAY_LOGS_BUFFER_DB_PATH, dont_retry=True)
        if gateway_logs_buffer_db.db_unavailable:
            gateway_logs_buffer_db = None

    # attempt to publish log message via MQTT
    publish_failure = False
    try:
        if not GatewayMqttClient().publish_log(level, message):
            publish_failure = True
            print(f'Failed to publish log message via MQTT.')
    except Exception as e:
        publish_failure = True
        print(f'Failed to publish log message via MQTT: {e}')

    # buffer unpublished message in sqlite db to be published later
    if publish_failure and gateway_logs_buffer_db is not None:
        print(f'Buffering unpublished message.')
        gateway_logs_buffer_db.execute("""
            CREATE TABLE IF NOT EXISTS log_buffer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_level text,
                message text,
                timestamp_ms INTEGER
            );
        """)
        gateway_logs_buffer_db.execute(
            "INSERT INTO log_buffer (log_level, message, timestamp_ms) VALUES (?, ?, ?)",
            (level, message, int(time.time_ns() / 1000_000))
        )

def debug(message: str):
    log('DEBUG', message)

def info(message: str):
    log('INFO', message)

def error(message: str):
    log('ERROR', message)

def warn(message: str):
    log('WARN', message)