import ssl
import json
import time
from queue import Queue

from paho.mqtt.client import Client

from utils.misc import fatal_error

GatewayMqttClientInstance = None

class GatewayMqttClient(Client):
    initialized = False
    connected = False
    message_queue = Queue.queue()

    @staticmethod
    def instance():
        global GatewayMqttClientInstance
        if GatewayMqttClientInstance is None:
            GatewayMqttClientInstance = GatewayMqttClient.__new__(GatewayMqttClient)
        return GatewayMqttClientInstance

    def __init__(self):
        super().__init__()
        GatewayMqttClient.__call__(self)

    def __call__(self, *args, **kwargs):
        fatal_error("GatewayMqttClient is a singleton and cannot be instantiated directly. "
                           "Use GatewayMqttClient.instance() instead.")

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

        return self

    def graceful_exit(self) -> None:
        print("Exiting MQTT-client gracefully...")
        self.disconnect()
        self.loop_stop()

    def __on_connect(self, _client, _userdata, _flags, _result_code, *_extra_params) -> None:
        if _result_code != 0:
            print(f"Failed to connect to ThingsBoard with result code: {_result_code}")
            self.graceful_exit()
            return

        print("Successfully connected to ThingsBoard!")
        self.subscribe("v1/devices/me/rpc/request/+")
        self.subscribe("v1/devices/me/attributes/response/+")
        self.subscribe("v1/devices/me/attributes")
        self.subscribe("v2/fw/response/+")

        self.publish('v1/devices/me/attributes/request/1', '{"sharedKeys":"sw_title,sw_url,sw_version,controller_config"}')
        self.connected = True

    def __on_disconnect(self, _client, _userdata, result_code) -> None:
        self.connected = False
        print(f"Disconnected from ThingsBoard with result code: {result_code}")
        self.graceful_exit()

    def __on_message(self, _client, _userdata, msg) -> None:
        self.message_queue.put({
            "topic": msg.topic,
            "payload": json.loads(msg.payload)
        })

    def publish_message(self, message: str) -> bool:
        return self.publish_message_raw("v1/devices/me/telemetry", message)

    def publish_message_raw(self, topic: str, message: str) -> bool:
        if not self.initialized or not self.connected:
            print(f'MQTT client is not connected/initialized, cannot publish message "{message}" to topic "{topic}"')
            return False
        print(f'Publishing message: {message}')
        self.publish(topic, message)
        return True

    def publish_log(self, log_level, log_message) -> None:
        self.publish_message(json.dumps({
            "ts": int(time.time()) * 1000,
            "values": {
                "severity": log_level,
                "message": "GATEWAY - " + log_message
            }
        }))