import os
import time
import paho.mqtt.client
import ssl
from src import custom_types


class MQTTClient:
    """provides an mqtt client"""

    __config: custom_types.MQTTConfig | None = None
    __client: paho.mqtt.client.Client | None = None

    @staticmethod
    def init(timeout_seconds: float = 5) -> None:
        """v and
        initializes the mqtt client. timeout_seconds is the amount
        of time the mqtt connection process is allowed to take."""
        MQTTClient.__init_config()
        MQTTClient.__init_client(timeout_seconds=timeout_seconds)

    @staticmethod
    def get_config() -> custom_types.MQTTConfig:
        """returns the mqtt config, requires init() to be run before"""
        assert (
            MQTTClient.__config is not None
        ), "please run init() before requesting the config"
        return MQTTClient.__config

    @staticmethod
    def get_client() -> paho.mqtt.client.Client:
        """returns the mqtt client, requires init() to be run before"""
        assert (
            MQTTClient.__client is not None
        ), "please run init() before requesting the client"
        return MQTTClient.__client

    @staticmethod
    def deinit() -> None:
        """disconnected the mqtt client and removes the internal class state"""
        assert (
            MQTTClient.__client is not None
        ), "please run init() before requesting the client"
        MQTTClient.__client.disconnect()
        MQTTClient.__client = None
        MQTTClient.__config = None

    @staticmethod
    def __init_config() -> None:
        """loads the mqtt config from environment variables"""
        MQTTClient.__config = custom_types.MQTTConfig(
            station_identifier=os.environ.get("INSERT_NAME_HERE_STATION_IDENTIFIER"),
            mqtt_url=os.environ.get("INSERT_NAME_HERE_MQTT_URL"),
            mqtt_port=os.environ.get("INSERT_NAME_HERE_MQTT_PORT"),
            mqtt_username=os.environ.get("INSERT_NAME_HERE_MQTT_USERNAME"),
            mqtt_password=os.environ.get("INSERT_NAME_HERE_MQTT_PASSWORD"),
            mqtt_base_topic=os.environ.get("INSERT_NAME_HERE_MQTT_BASE_TOPIC"),
        )

    @staticmethod
    def __init_client(timeout_seconds: float = 5) -> None:
        """initializes the mqtt client. timeout_seconds is the amount
        of time the mqtt connection process is allowed to take."""
        assert MQTTClient.__config is not None

        mqtt_client = paho.mqtt.client.Client(
            client_id=MQTTClient.__config.station_identifier
        )
        mqtt_client.username_pw_set(
            MQTTClient.__config.mqtt_username, MQTTClient.__config.mqtt_password
        )
        mqtt_client.tls_set(
            certfile=None,
            keyfile=None,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        mqtt_client.connect(
            MQTTClient.__config.mqtt_url,
            port=int(MQTTClient.__config.mqtt_port),
            keepalive=60,
        )
        mqtt_client.loop_start()

        start_time = time.time()
        while True:
            if mqtt_client.is_connected():
                break
            if (time.time() - start_time) > timeout_seconds:
                raise TimeoutError(
                    f"mqtt client is not connected (using params {MQTTClient.config})"
                )
            time.sleep(0.1)

        MQTTClient.__client = mqtt_client
