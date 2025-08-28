import ssl
import json
import time
from queue import Queue
from typing import Any, Optional, Union

from paho.mqtt.client import Client

from modules.logging import info, error, debug, warn

singleton_instance : Optional["GatewayMqttClient"] = None

class GatewayMqttClient(Client):
    attribute_request_id: int = 0
    initialized = False
    connected = False
    message_queue : Queue = Queue()

    def __init__(self):
        global singleton_instance
        if singleton_instance is None:
            debug("[MQTT] Initializing GatewayMqttClient")
            super().__init__()
            singleton_instance = self

    # Singleton pattern
    def __new__(cls: Any) -> "GatewayMqttClient":
        global singleton_instance
        if singleton_instance is not None:
            return singleton_instance
        return super(GatewayMqttClient, cls).__new__(cls)

    def init(self, access_token: str):
        super().__init__()

        # set up the client
        self.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.username_pw_set(access_token, "")

        # set up the callbacks
        self.on_connect = self.__on_connect
        self.on_message = self.__on_message
        self.on_disconnect = self.__on_disconnect

        self.initialized = True
        self.connected = False
        self.attribute_request_id = 0

        return self

    def graceful_exit(self) -> None:
        info("[MQTT] Exiting MQTT-client gracefully...")
        self.disconnect()
        self.loop_stop()

    def __on_connect(self, _client, _userdata, _flags, _result_code, *_extra_params) -> None:
        if _result_code != 0:
            error(f"[MQTT] Failed to connect to ThingsBoard with result code: {_result_code}")
            self.graceful_exit()
            return

        info("Successfully connected to ThingsBoard!")
        self.subscribe("v1/devices/me/rpc/request/+")
        self.subscribe("v1/devices/me/attributes/response/+")
        self.subscribe("v1/devices/me/attributes")
        self.subscribe("v2/fw/response/+")

        self.connected = True
        self.request_attributes({"sharedKeys": "sw_title,sw_url,sw_version,FILES"})

    def __on_disconnect(self, _client, _userdata, result_code) -> None:
        self.connected = False
        info(f"[MQTT] Disconnected from ThingsBoard with result code: {result_code}")
        self.graceful_exit()

    def __on_message(self, _client, _userdata, msg) -> None:
        self.message_queue.put({
            "topic": msg.topic,
            "payload": json.loads(msg.payload)
        })

    def publish_sw_state(self, version: str, state: str, msg : Optional[str]=None) -> None:
        self.publish_telemetry(json.dumps({
            "current_sw_title": version,
            "current_sw_version": version,
            "sw_state": state,
            "sw_error": msg or ""
        }))

    def publish_telemetry(self, message: str) -> bool:
        return self.publish_message_raw("v1/devices/me/telemetry", message)

    def publish_message_raw(self, topic: str, message: str) -> bool:
        if not self.initialized or not self.connected:
            print(f'[MQTT] MQTT client is not connected/initialized, cannot publish message "{message}" to topic "{topic}"')
            return False
        debug(f'[MQTT] Publishing message: {message}')
        try:
            self.publish(topic, message).wait_for_publish(5)
        except Exception as e:
            print(f'[MQTT] Failed to publish message "{message}" to topic "{topic}": {e}')
            return False

        return True

    def request_attributes(self, request_dict: dict) -> bool:
        self.attribute_request_id += 1
        return self.publish_message_raw(f"v1/devices/me/attributes/request/{str(self.attribute_request_id)}",
                                 json.dumps(request_dict))

    def publish_log(self, log_level, log_message, timestamp_ms = None) -> bool:
        time.sleep(1/1000) # sleep for 1ms to avoid duplicate timestamps
        return self.publish_telemetry(json.dumps({
            "ts": timestamp_ms or int(time.time_ns() / 1000_000),
            "values": {
                "severity": log_level,
                "message": "GATEWAY - " + log_message
            }
        }))

    def update_sys_info_attribute(self) -> None:
        sys_info_data = {}
        try:
            with open('/proc/stat', 'r') as f:
                lines = f.readlines()
                for line in lines:
                    sys_info_data[line.split()[0]] = line.split()[1:]
        except Exception as e:
            warn(f"Failed to read /proc/stat: {e}")

        self.publish_message_raw("v1/devices/me/attributes", json.dumps({
            "sys_info": sys_info_data
        }))