import json
import os
import signal
import sys
import threading
from logging import error
from time import sleep, time_ns
from typing import Any, Optional

from modules.file_writer import GatewayFileWriter
from modules.logging import info, warn, debug
import utils.paths
import utils.misc
from args import parse_args
from modules import sqlite
from modules.docker_client import GatewayDockerClient
from modules.git_client import GatewayGitClient
from modules.mqtt import GatewayMqttClient
from on_mqtt_msg.check_for_file_content_update import on_msg_check_for_file_content_update
from on_mqtt_msg.check_for_file_hashes_update import on_msg_check_for_file_hashes_update, FILE_HASHES_TB_KEY
from on_mqtt_msg.check_for_files_definition_update import on_msg_check_for_files_definition_update
from on_mqtt_msg.check_for_ota_updates import on_msg_check_for_ota_update
from on_mqtt_msg.on_rpc_request import on_rpc_request
from self_provisioning import self_provisioning_get_access_token
from utils.controller_restart import restart_controller_if_needed
from utils.misc import get_maybe

global_mqtt_client : Optional[GatewayMqttClient] = None
archive_sqlite_db = None
communication_sqlite_db = None
gateway_logs_buffer_db = None
STOP_MAINLOOP = False
AUX_DATA_PUBLISH_INTERVAL_MS = 20_000 # every 20 seconds
aux_data_publish_ts = None


# Set up signal handling for safe shutdown
def shutdown_handler(sig: Any, _frame: Any) -> None:
    global STOP_MAINLOOP
    """Handle program exit gracefully"""
    # Set a timer to force exit if a graceful shutdown fails
    signal.setitimer(signal.ITIMER_REAL, 20)

    info("GRACEFUL SHUTDOWN")
    STOP_MAINLOOP = True
    if global_mqtt_client is not None:
        global_mqtt_client.graceful_exit()
    if archive_sqlite_db is not None:
        archive_sqlite_db.close()
    if communication_sqlite_db is not None:
        communication_sqlite_db.close()
    if gateway_logs_buffer_db is not None:
        gateway_logs_buffer_db.close()

    sys.stdout.flush()
    sys.exit(sig)


# Set up signal handling for forced shutdown in case graceful shutdown fails
def forced_shutdown_handler(_sig: Any, _frame: Any) -> None:
    warn("FORCEFUL SHUTDOWN")
    sys.stdout.flush()
    os._exit(1)


def get_last_controller_health_check_ts():
    if communication_sqlite_db.do_table_values_exist(sqlite.SqliteTables.HEALTH_CHECK.value):
        last_controller_health_check_ts_result = communication_sqlite_db.execute(
            "SELECT timestamp_ms FROM health_check WHERE id = 1")
        if len(last_controller_health_check_ts_result) > 0:
            return last_controller_health_check_ts_result[0][0]

    return 0

signal.signal(signal.SIGALRM, forced_shutdown_handler)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


try:
    if __name__ == '__main__':
        # setup
        docker_client: GatewayDockerClient = GatewayDockerClient()
        git_client: GatewayGitClient = GatewayGitClient()
        args = parse_args()
        debug(f"Args: {args}")
        provisioned, access_token = self_provisioning_get_access_token(args)

        # initialize sqlite database connections
        archive_sqlite_db = sqlite.SqliteConnection(utils.paths.GATEWAY_ARCHIVE_DB_PATH)
        communication_sqlite_db = sqlite.SqliteConnection(utils.paths.COMMUNICATION_QUEUE_DB_PATH)
        gateway_logs_buffer_db = sqlite.SqliteConnection(utils.paths.GATEWAY_LOGS_BUFFER_DB_PATH)
        archive_sqlite_db.execute("""
                CREATE TABLE IF NOT EXISTS controller_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_ms INTEGER,
                    message TEXT
                );
            """)
        archive_sqlite_db.execute("CREATE INDEX IF NOT EXISTS controller_archive_ts_index on controller_archive (timestamp_ms);")
        communication_sqlite_db.execute(f"""
            CREATE TABLE IF NOT EXISTS {sqlite.SqliteTables.CONTROLLER_MESSAGES.value} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type text,
                message text
            );
        """)
        communication_sqlite_db.execute(f"""      
            CREATE TABLE IF NOT EXISTS {sqlite.SqliteTables.PENDING_MQTT_MESSAGES.value} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type text,
                message text
            );
        """)


        # create and run the mqtt client in a separate thread
        mqtt_client = GatewayMqttClient().init(access_token)
        try:
            mqtt_client.connect(args.tb_host, args.tb_port)
        except Exception as e:
            error(f"Failed to connect to ThingsBoard: {e}")
        mqtt_client_thread: threading.Thread = threading.Thread(
            target=lambda: mqtt_client.loop_forever())
        mqtt_client_thread.start()
        global_mqtt_client = mqtt_client

        sleep(5)

        info("Gateway started successfully")

        if provisioned:
            info("Gateway is provisioned for first time, initializing attributes...")
            GatewayMqttClient().publish_message_raw("v1/devices/me/attributes", json.dumps({ FILE_HASHES_TB_KEY: {}}))

        # daemon thread for updating file content client attributes every 30 seconds
        def file_update_check_daemon():
            """Daemon thread to check for file updates every 30 seconds."""
            while True:
                sleep(30)
                try:
                    debug("Checking for file changes...")
                    file_definitions = GatewayFileWriter().get_files()
                    for file_id in file_definitions:
                        if GatewayFileWriter().did_file_change(get_maybe(file_definitions, file_id, "path")):
                            info(f"File {file_definitions[file_id]} changed on disk - requesting update")
                            GatewayMqttClient().request_attributes({"clientKeys": FILE_HASHES_TB_KEY})
                except Exception as ex:
                    warn(f"Error checking for file changes: {ex}")
        file_update_thread = threading.Thread(target=file_update_check_daemon, daemon=True)
        file_update_thread.start()

        # *** main loop ***
        while not STOP_MAINLOOP:
            # check if there are any new incoming mqtt messages in the queue, process them
            if not mqtt_client.message_queue.empty():
                msg = mqtt_client.message_queue.get()
                topic = get_maybe(msg, "topic") or "unknown"
                msg_payload = utils.misc.get_maybe(msg, "payload")

                # check for incoming RPC requests
                if "v1/devices/me/rpc/request" in topic:
                    rpc_method = get_maybe(msg_payload, "method")
                    rpc_params = get_maybe(msg_payload, "params")
                    rpc_msg_id = topic.split("/")[-1]
                    on_rpc_request(rpc_msg_id, rpc_method, rpc_params)

                # check for attribute updates
                elif "v1/devices/me/attributes" in topic:
                    if not any([
                            on_msg_check_for_ota_update(msg_payload),
                            on_msg_check_for_files_definition_update(msg_payload),
                            on_msg_check_for_file_hashes_update(msg_payload),
                            on_msg_check_for_file_content_update(msg_payload),
                    ]):
                        warn("[MAIN] Got invalid message: " + str(msg))
                        warn("[MAIN] Skipping invalid message...")

                continue  # process the next message

            # automatically restart the controller's docker container if it is not running
            if restart_controller_if_needed():
                continue

            if not mqtt_client_thread.is_alive() or not mqtt_client.is_connected():
                if not mqtt_client.is_connected():
                    warn("MQTT client not connected, exiting in 30 seconds...")
                else:
                    warn("MQTT client thread died, exiting in 30 seconds...")
                sleep(30)
                utils.misc.fatal_error("MQTT client thread died")

            # check if there is any buffered outgoing log message in the buffer sqlite db
            if gateway_logs_buffer_db.do_table_values_exist("log_buffer"):
                # fetch the next message (lowest `id`) from the queue and send it
                message = gateway_logs_buffer_db.execute(
                    f"SELECT id, log_level, message, timestamp_ms FROM {"log_buffer"} ORDER BY id LIMIT 1")
                if len(message) > 0:
                    debug('Sending buffered log message: ' + str(message[0]))
                    if not mqtt_client.publish_log(message[0][1], message[0][2], message[0][3]):
                        continue
                    gateway_logs_buffer_db.execute(f"DELETE FROM {"log_buffer"} WHERE id = {message[0][0]}")
                continue


            if communication_sqlite_db.do_table_values_exist(sqlite.SqliteTables.CONTROLLER_MESSAGES.value):
                # fetch the next message (lowest `id`) from the queue and process it
                message = communication_sqlite_db.execute(
                    f"SELECT id, type, message FROM {sqlite.SqliteTables.CONTROLLER_MESSAGES.value} ORDER BY id LIMIT 1"
                )
                if len(message) > 0:
                    message_type = message[0][1]
                    message_obj = json.loads(message[0][2])
                    message_timestamp_ms = message_obj["ts"]
                    message_values = message_obj["values"]

                    # archive controller messages in the archive sqlite db, except for log messages
                    if not "log" in message_type:
                        archive_sqlite_db.execute(
                            "INSERT INTO controller_archive (timestamp_ms, message) VALUES (?, ?)",
                            (message_timestamp_ms, json.dumps(message_values)))

                    # add message to sqlite table containing pending outgoing mqtt messages
                    communication_sqlite_db.execute(
                        "INSERT INTO " + sqlite.SqliteTables.PENDING_MQTT_MESSAGES.value + " (type, message) VALUES (?, ?)",
                        (message[0][1], message[0][2]))

                    # remove the published message from the queue
                    communication_sqlite_db.execute(
                        f"DELETE FROM {sqlite.SqliteTables.CONTROLLER_MESSAGES.value} WHERE id = {message[0][0]}")
                continue

            # check if there are any new outgoing mqtt messages in the sqlite db
            if communication_sqlite_db.do_table_values_exist(sqlite.SqliteTables.PENDING_MQTT_MESSAGES.value):
                # fetch the next message (lowest `id`) from the queue and send it
                message = communication_sqlite_db.execute(
                    f"SELECT id, type, message FROM {sqlite.SqliteTables.PENDING_MQTT_MESSAGES.value} ORDER BY id LIMIT 1"
                )
                if len(message) > 0:
                    message_type = message[0][1]
                    message_obj = json.loads(message[0][2])
                    debug('Sending controller message: ' + str(message[0]))
                    if not mqtt_client.publish_telemetry(message[0][2]):
                        continue

                    # remove the published message from the queue
                    communication_sqlite_db.execute(
                        f"DELETE FROM {sqlite.SqliteTables.PENDING_MQTT_MESSAGES.value} WHERE id = {message[0][0]}")
                continue

            controller_running_since_ts = docker_client.get_edge_startup_timestamp_ms() or 0
            last_controller_health_check_ts = get_last_controller_health_check_ts()

            # publish controller startup time and health check time to mqtt
            if aux_data_publish_ts is None or int(time_ns() / 1_000_000) - aux_data_publish_ts > AUX_DATA_PUBLISH_INTERVAL_MS:
                aux_data_publish_ts = int(time_ns() / 1_000_000)
                mqtt_client.publish_telemetry(json.dumps({
                    "ts": aux_data_publish_ts,
                    "values": {
                        "ms_since_controller_startup": aux_data_publish_ts - controller_running_since_ts,
                        "ms_since_last_controller_health_check": aux_data_publish_ts - last_controller_health_check_ts
                    }
                }))

            if (max(last_controller_health_check_ts, controller_running_since_ts)
                    < int(time_ns() / 1_000_000) - (6 * 3600_000)
                    and docker_client.is_controller_running()):
                warn("Controller did not send health check in the last 6 hours, stopping container...")
                docker_client.stop_controller()
                continue

            # if nothing happened this iteration, sleep for a while
            sleep(5)

except Exception as e:
    utils.misc.fatal_error(f"An error occurred in gateway main loop: {e}")


