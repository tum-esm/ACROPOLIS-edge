import queue
import threading
from time import sleep

from args import parse_args
from data_connections import mqtt, sqlite
from self_provisioning import self_provisioning_get_access_token


if __name__ == '__main__':
    # setup
    mqtt_message_queue = queue.Queue()
    args = parse_args()
    access_token = self_provisioning_get_access_token(args)

    archive_sqlite_db = sqlite.SqliteConnection("archive.db")
    communication_sqlite_db = sqlite.SqliteConnection("communication.db")

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

        # check if there are any new mqtt messages in the queue
        if not mqtt_message_queue.empty():
            print("Got message: " + str(mqtt_message_queue.get()))
            continue

        # if nothing happened this iteration, sleep for a while
        sleep(1)

