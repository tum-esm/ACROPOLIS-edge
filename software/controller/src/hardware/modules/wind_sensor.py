import time

from custom_types import config_types, sensor_types
from custom_types import mqtt_playload_types
from interfaces import hardware_interface, logging_interface
from utils import message_queue


class WindSensorModule:
    """
    Optional module for the wind sensor.
    
    This module is responsible for:
    (1) Implementing the WXT532 sensor interface
    (2) Communicate out measurements to the edge gateway
    """

    #TODO: Make it executeable as a thread

    def __init__(
            self, config: config_types.Config,
            hardware_interface: hardware_interface.HardwareInterface) -> None:

        self.logger, self.config = logging_interface.Logger(
            config=config, origin="measurement-procedure"), config
        self.hardware_interface = hardware_interface

        # state variables
        self.message_queue = message_queue.MessageQueue()

    def process_wind_sensor_data(self) -> None:
        # wind measurement

        wind_sensor_data, wind_sensor_status = self.hardware_interface.wind_sensor.read(
        )

        self._send_wind_sensor_data(wind_sensor_data=wind_sensor_data)
        self._send_wind_sensor_status(wind_sensor_status=wind_sensor_status)

    def _send_wind_sensor_data(
            self, wind_sensor_data: sensor_types.WindSensorData) -> None:
        # send latest wind measurement info
        if wind_sensor_data is not None:
            self.logger.info(
                f"latest wind sensor measurement: {wind_sensor_data}")

            self.message_queue.enqueue_message(
                timestamp=int(time.time()),
                payload=mqtt_playload_types.MQTTWindData(
                    wxt532_direction_min=wind_sensor_data.direction_min,
                    wxt532_direction_avg=wind_sensor_data.direction_avg,
                    wxt532_direction_max=wind_sensor_data.direction_max,
                    wxt532_speed_min=wind_sensor_data.speed_min,
                    wxt532_speed_avg=wind_sensor_data.speed_avg,
                    wxt532_speed_max=wind_sensor_data.speed_max,
                    wxt532_last_update_time=wind_sensor_data.last_update_time,
                ),
            )
        else:
            self.logger.info(f"did not receive any wind sensor measurement")

    def _send_wind_sensor_status(
            self, wind_sensor_status: sensor_types.WindSensorStatus) -> None:
        # send latest wind sensor device info
        if wind_sensor_status is not None:
            self.logger.info(
                f"latest wind sensor device info: {wind_sensor_status}")

            self.message_queue.enqueue_message(
                timestamp=int(time.time()),
                payload=mqtt_playload_types.MQTTWindSensorInfo(
                    wxt532_temperature=wind_sensor_status.temperature,
                    wxt532_heating_voltage=wind_sensor_status.heating_voltage,
                    wxt532_supply_voltage=wind_sensor_status.supply_voltage,
                    wxt532_reference_voltage=wind_sensor_status.
                    reference_voltage,
                    wxt532_last_update_time=wind_sensor_status.
                    last_update_time,
                ),
            )

        else:
            self.logger.info(f"did not receive any wind sensor device info")
