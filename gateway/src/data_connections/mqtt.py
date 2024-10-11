import json
import ssl

from paho.mqtt.client import Client

class GatewayMqttClient(Client):
    def __init__(self, message_queue, access_token):
        super().__init__()

        # set up the client
        self.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.username_pw_set(access_token, "")

        # set up the callbacks
        self.on_connect = self.__on_connect
        self.on_message = self.__on_message
        self.on_disconnect = self.__on_disconnect
        self.message_queue = message_queue

    def graceful_exit(self):
        print("Exiting MQTT-client gracefully...")
        self.disconnect()
        self.loop_stop()

    def __on_connect(self, _client, _userdata, _flags, _result_code, *_extra_params):
        if _result_code != 0:
            print(f"Failed to connect to ThingsBoard with result code: {_result_code}")
            self.graceful_exit()
            return

        print("Successfully connected to ThingsBoard!")
        self.subscribe("v1/devices/me/attributes/response/+")
        self.subscribe("v1/devices/me/attributes")
        self.subscribe("v2/fw/response/+")

    def __on_disconnect(self, _client, _userdata, _rc):
        print(f"Disconnected from ThingsBoard with result code: {_rc}")
        self.graceful_exit()

    def __on_message(self, _client, _userdata, msg):
        self.message_queue.put({
            "topic": msg.topic,
            "payload": json.loads(msg.payload)
        })
