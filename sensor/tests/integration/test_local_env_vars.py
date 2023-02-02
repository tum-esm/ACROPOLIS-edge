import os
import sys
import pytest
import dotenv

dir = os.path.dirname
PROJECT_DIR = dir(dir(dir(os.path.abspath(__file__))))
sys.path.append(PROJECT_DIR)
from src import custom_types, utils


@pytest.mark.integration
def test_lcoal_env_vars() -> None:
    """checks whether the local config/.env can be loaded"""

    dotenv.load_dotenv(os.path.join(PROJECT_DIR, "config", ".env"))

    custom_types.MQTTConfig(
        station_identifier=utils.get_hostname(),
        mqtt_url=os.environ.get("INSERT_NAME_HERE_MQTT_URL"),
        mqtt_port=os.environ.get("INSERT_NAME_HERE_MQTT_PORT"),
        mqtt_username=os.environ.get("INSERT_NAME_HERE_MQTT_USERNAME"),
        mqtt_password=os.environ.get("INSERT_NAME_HERE_MQTT_PASSWORD"),
        mqtt_base_topic=os.environ.get("INSERT_NAME_HERE_MQTT_BASE_TOPIC"),
    )