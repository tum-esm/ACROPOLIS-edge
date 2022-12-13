from os.path import dirname, abspath
import sys
import pytest
from ..pytest_fixtures import log_files

PROJECT_DIR = dirname(dirname(abspath(__file__)))
sys.path.append(PROJECT_DIR)
from src import interfaces


@pytest.mark.integration
def test_mainboard_sensor(log_files) -> None:
    sensor = interfaces.MainboardSensorInterface()
    sensor.get_system_data()
