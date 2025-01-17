import os
import queue
import signal
import sys
import threading
from time import sleep

import utils.paths
import utils.misc
from args import parse_args
from modules import sqlite, docker_client, git_client
from modules import mqtt
from on_mqtt_msg.check_for_config_update import on_msg_check_for_config_update
from on_mqtt_msg.check_for_ota_updates import on_msg_check_for_ota_update
from self_provisioning import self_provisioning_get_access_token

mqtt_client = None
archive_sqlite_db = None
communication_sqlite_db = None

# Set up signal handling for safe shutdown
def shutdown_handler(sig, frame):
    """Handle program exit gracefully"""
    # Set a timer to force exit if graceful shutdown fails
    signal.setitimer(signal.ITIMER_REAL, 20)

    print("GRACEFUL SHUTDOWN")
    if mqtt_client is not None:
        mqtt_client.graceful_exit()
    if archive_sqlite_db is not None:
        archive_sqlite_db.close()
    if communication_sqlite_db is not None:
        communication_sqlite_db.close()

    sys.stdout.flush()
    sys.exit(sig)

# Set up signal handling for forced shutdown in case graceful shutdown fails
def forced_shutdown_handler(sig, frame):
    print("FORCEFUL SHUTDOWN")
    sys.stdout.flush()
    os._exit(1)
signal.signal(signal.SIGALRM, forced_shutdown_handler)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

try:
    if __name__ == '__main__':
        # setup
        mqtt_message_queue = queue.Queue()
        docker_client = docker_client.GatewayDockerClient()
        git_client = git_client.GatewayGitClient()
        args = parse_args()
        print(f"Args: {args}")
        access_token = self_provisioning_get_access_token(args)

        archive_sqlite_db = sqlite.SqliteConnection("archive.db")
        comm_db_path = os.path.join(utils.paths.ACROPOLIS_DATA_PATH, "acropolis_comm_db.db")
        print(f"Comm DB path: {comm_db_path}")
        communication_sqlite_db = sqlite.SqliteConnection(comm_db_path)

        # create and run the mqtt client in a separate thread
        mqtt_client = mqtt.GatewayMqttClient.instance().init(mqtt_message_queue, access_token)
        mqtt_client.connect(args.tb_host, args.tb_port)
        mqtt_client_thread = threading.Thread(target=lambda: mqtt_client.loop_forever())
        mqtt_client_thread.start()

        sleep(5)

        while True:
            # check if there are any new incoming mqtt messages in the queue, process them
            if not mqtt_message_queue.empty():
                msg = mqtt_message_queue.get()
                msg_payload = utils.misc.get_maybe(msg, "payload", "shared") or utils.misc.get_maybe(msg, "payload")
                if not on_msg_check_for_ota_update(msg_payload) \
                        and not on_msg_check_for_config_update(msg_payload):
                    print("Got message: " + str(msg))
                    print("Invalid message, skipping...")
                continue # process next message

            if not docker_client.is_edge_running():
                print("Controller is not running, starting new container...")
                docker_client.start_edge()

            if not mqtt_client_thread.is_alive():
                print("MQTT client thread died, exiting in 30 seconds...")
                sleep(30)
                exit()

            # check if there are any new outgoing mqtt messages in the sqlite db
            if (communication_sqlite_db.does_table_exist(sqlite.SqliteTables.QUEUE_OUT.value)
                    and not communication_sqlite_db.is_table_empty(sqlite.SqliteTables.QUEUE_OUT.value)):
                # fetch the next message (lowest `id) from the queue and send it
                message = communication_sqlite_db.execute(
                    f"SELECT * FROM {sqlite.SqliteTables.QUEUE_OUT.value} ORDER BY id LIMIT 1")
                if len(message) > 0:
                    print('Sending message: ' + str(message[0]))
                    if not mqtt_client.publish_message(message[0][2]):
                        continue
                    communication_sqlite_db.execute(f"DELETE FROM {sqlite.SqliteTables.QUEUE_OUT.value} WHERE id = {message[0][0]}")
                continue

            # if nothing happened this iteration, sleep for a while
            sleep(1)

except Exception as e:
    utils.misc.fatal_error(f"An error occurred in gateway main loop: {e}")

