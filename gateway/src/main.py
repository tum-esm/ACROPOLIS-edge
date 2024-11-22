import inspect
import os
import queue
import signal
import sys
import threading
from time import sleep

from args import parse_args
from modules import mqtt, sqlite, docker_client, git_client
from self_provisioning import self_provisioning_get_access_token
from utils.misc import get_maybe

mqtt_client = None
archive_sqlite_db = None
communication_sqlite_db = None

# Set up signal handling for safe shutdown
def shutdown_handler(sig, frame):
    """Handle program exit gracefully"""
    # Set a timer to force exit if graceful shutdown fails
    signal.setitimer(signal.ITIMER_REAL, 20)

    if mqtt_client is not None:
        mqtt_client.graceful_exit()
    if archive_sqlite_db is not None:
        archive_sqlite_db.close()
    if communication_sqlite_db is not None:
        communication_sqlite_db.close()

    sys.exit(sig)

# Set up signal handling for forced shutdown in case graceful shutdown fails
def forced_shutdown_handler():
    print("FORCEFUL SHUTDOWN")
    sys.stdout.flush()
    os._exit()
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
        access_token = self_provisioning_get_access_token(args)

        archive_sqlite_db = sqlite.SqliteConnection("archive.db")
        communication_sqlite_db = sqlite.SqliteConnection(os.environ.get("ACROPOLIS_COMMUNICATION_DB_PATH") or "communication.db")

        # create and run the mqtt client in a separate thread
        mqtt_client = mqtt.GatewayMqttClient(mqtt_message_queue, access_token)
        mqtt_client.connect(args.tb_host, args.tb_port)
        mqtt_client_thread = threading.Thread(target=lambda: mqtt_client.loop_forever())
        mqtt_client_thread.start()

        while True:
            if not mqtt_client_thread.is_alive():
                print("MQTT client thread died, exiting in 30 seconds...")
                sleep(30)
                exit()

            # check if there are any new incoming mqtt messages in the queue
            if not mqtt_message_queue.empty():
                msg = mqtt_message_queue.get()
                sw_title = get_maybe(msg, "payload", "shared", "sw_title")
                sw_url = get_maybe(msg, "payload", "shared", "sw_url")
                sw_version = get_maybe(msg, "payload", "shared", "sw_version")
                if sw_title is not None and sw_url is not None and sw_version is not None:
                    if docker_client.is_edge_running():
                        current_version = docker_client.get_edge_version()
                        if current_version is not None and current_version != sw_version:
                            print("Software update available: " + sw_title + " from " + current_version + " to " + sw_version)
                            docker_client.start_edge(sw_version)
                        else:
                            print("Software is up to date")
                    else:
                        print("Launching latest edge-software: " + sw_version + " (" + sw_title + ")")
                        docker_client.start_edge(sw_version)
                else:
                    print("Got message: " + str(msg))
                    print("Invalid message, skipping...")
                continue

            # check if there are any new outgoing mqtt messages in the sqlite db
            if not communication_sqlite_db.is_table_empty(sqlite.SqliteTables.QUEUE_OUT.value):
                # fetch the next message (lowest `id) from the queue and send it
                message = communication_sqlite_db.execute(
                    f"SELECT * FROM {sqlite.SqliteTables.QUEUE_OUT.value} ORDER BY id LIMIT 1")
                if len(message) > 0:
                    print("Sending message: " + str(message[0]))
                    mqtt_client.publish_message(message[0][1])
                    communication_sqlite_db.execute(f"DELETE FROM {sqlite.SqliteTables.QUEUE_OUT.value} WHERE id = {message[0][0]}")
                continue

            # if nothing happened this iteration, sleep for a while
            sleep(1)
except Exception as e:
    print(f"An error occurred in gateway main loop: {e}")
    shutdown_handler(1, inspect.currentframe())
