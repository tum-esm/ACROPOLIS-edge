from os import path, environ
from os.path import dirname, join

from modules.logging import debug

PROJECT_DIR = dirname(dirname(dirname(path.abspath(__file__)))) # path to "gateway" folder
GATEWAY_DATA_PATH = str(environ.get("ACROPOLIS_DATA_PATH") or join(dirname(PROJECT_DIR)))
CONTROLLER_LOGS_PATH = str(environ.get("ACROPOLIS_CONTROLLER_LOGS_PATH") or join(dirname(dirname(PROJECT_DIR)), "logs"))
GATEWAY_GIT_PATH = str(environ.get("ACROPOLIS_GATEWAY_GIT_PATH") or join(dirname(dirname(PROJECT_DIR)), ".git"))

GATEWAY_LOGS_BUFFER_DB_NAME = "gateway_logs_buffer.db"
GATEWAY_LOGS_BUFFER_DB_PATH = join(str(GATEWAY_DATA_PATH), GATEWAY_LOGS_BUFFER_DB_NAME)

GATEWAY_ARCHIVE_DB_NAME = "gateway_archive.db"
GATEWAY_ARCHIVE_DB_PATH = join(str(GATEWAY_DATA_PATH), GATEWAY_ARCHIVE_DB_NAME)

COMMUNICATION_QUEUE_DB_NAME = "communication_queue.db"
COMMUNICATION_QUEUE_DB_PATH = str(environ.get("TEG_COMMUNICATION_QUEUE_DB_PATH") or join(str(GATEWAY_DATA_PATH), COMMUNICATION_QUEUE_DB_NAME))

debug(f'PROJECT_DIR: {PROJECT_DIR}')
debug(f'GATEWAY_DATA_PATH: {GATEWAY_DATA_PATH}')
debug(f'CONTROLLER_LOGS_PATH: {CONTROLLER_LOGS_PATH}')
debug(f'GATEWAY_GIT_PATH: {GATEWAY_GIT_PATH}')

debug(f'GATEWAY_LOGS_BUFFER_DB_PATH: {GATEWAY_LOGS_BUFFER_DB_PATH}')
debug(f'GATEWAY_ARCHIVE_DB_PATH: {GATEWAY_ARCHIVE_DB_PATH}')
debug(f'COMMUNICATION_QUEUE_DB_PATH: {COMMUNICATION_QUEUE_DB_PATH}')