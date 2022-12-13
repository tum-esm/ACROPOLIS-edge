import multiprocessing
import queue
import json
import os
import time
import pytest
from os.path import dirname, abspath, join
import sys

from fixtures import mqtt_client_environment, log_files
from utils import expect_log_lines, wait_for_condition

PROJECT_DIR = dirname(dirname(dirname(abspath(__file__))))
LOG_FILE = join(PROJECT_DIR, "logs", "current-logs.log")
sys.path.append(PROJECT_DIR)

from src import utils, interfaces


@pytest.mark.ci
def test_mqtt_receiving(mqtt_client_environment) -> None:
    global exception_queue

    mqtt_config = utils.mqtt.get_mqtt_config()
    config_topic = (
        f"{mqtt_config.mqtt_base_topic}/configuration/{mqtt_config.station_identifier}"
    )
    message = {"hello": f"you {round(time.time())/32}"}
    print(f"config_topic = {config_topic}")

    expect_log_lines(
        forbidden_lines=[
            f"mqtt-receiving-client - INFO - subscribing to topic {config_topic}",
        ]
    )

    receiving_client = interfaces.ReceivingMQTTClient()
    assert len(receiving_client.get_messages()) == 0
    time.sleep(1)

    expect_log_lines(
        required_lines=[
            f"mqtt-receiving-client - INFO - subscribing to topic {config_topic}",
        ]
    )

    assert receiving_client.mqtt_client.is_connected()

    message_info = receiving_client.mqtt_client.publish(
        topic=config_topic, payload=json.dumps(message), qos=1
    )
    wait_for_condition(
        is_successful=lambda: message_info.is_published(),
        timeout_message=f"message if mid {message_info.mid} could not be published",
    )

    time.sleep(1)
    assert receiving_client.mqtt_client.is_connected()

    expect_log_lines(
        required_lines=[
            f"mqtt-receiving-loop - DEBUG - received message: ",
        ]
    )

    messages = receiving_client.get_messages()
    print(f"mesages = {messages}")
    assert messages == [{"topic": config_topic, "payload": message}]