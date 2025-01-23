from typing import Any, Dict
import time

from custom_types import config_types, sensor_types, mqtt_playload_types
from interfaces import logging_interface
from utils import ring_buffer, message_queue
from utils.extract_true_bottle_value import extract_true_bottle_value
from hardware.sensors.vaisala_gmp343 import VaisalaGMP343
from hardware.sensors.bosch_bme280 import BoschBME280
from hardware.sensors.sensirion_sht45 import SensirionSHT45


class CO2MeasurementModule:
    """Combines sensor and actor interfaces."""

    def __init__(self, config: config_types.Config, co2_sensor: VaisalaGMP343,
                 inlet_bme280: BoschBME280,
                 inlet_sht45: SensirionSHT45) -> None:

        self.logger = logging_interface.Logger(config=config,
                                               origin="CO2MeasurementModule")
        self.config = config
        self.message_queue = message_queue.MessageQueue()
        self.reset_ring_buffers()
        self.calibration_reading: Dict[Any, Any] = {}
        self.slope = 1
        self.offset = 0

        # hardware
        self.co2_sensor = co2_sensor
        self.inlet_bme280 = inlet_bme280
        self.inlet_sht45 = inlet_sht45

    def perform_CO2_measurement(self) -> Any:
        """do regular measurements for in config defined measurement interval"""

        # Get latest auxiliary sensor data information
        self._update_air_inlet_parameters()

        # perform a CO2 measurement
        CO2_sensor_data = (self.co2_sensor.read_with_retry(
            timeout=60,
            pressure=self.rb_pressure.avg(),
            humidity=self.rb_humidity.avg(),
        ))
        self.logger.debug(f"new measurement: {CO2_sensor_data}")

        return CO2_sensor_data

    def _update_air_inlet_parameters(self) -> None:
        """
        fetches the latest temperature and pressure data at air inlet
        """

        self.air_inlet_bme280_data = (self.inlet_bme280.read_with_retry())

        # Add to ring buffer to calculate moving average of low-cost sensor
        self.rb_pressure.append(self.air_inlet_bme280_data.pressure)

        self.air_inlet_sht45_data = (self.inlet_sht45.read_with_retry())

        # Add to ring buffer to calculate moving average of low-cost sensor
        self.rb_humidity.append(self.air_inlet_sht45_data.humidity)

    def reset_ring_buffers(self) -> None:
        self.rb_pressure = ring_buffer.RingBuffer(
            self.config.measurement.average_air_inlet_measurements)
        self.rb_humidity = ring_buffer.RingBuffer(
            self.config.measurement.average_air_inlet_measurements)
        self.calibration_co2_buffer = ring_buffer.RingBuffer(
            int(self.config.calibration.sampling_per_cylinder_seconds /
                self.config.hardware.gmp343_filter_seconds_averaging))

    def log_cylinder_median(self, bottle_id: int, median: float) -> None:
        self.calibration_reading[bottle_id] = median
        self.logger.info(
            f"Calculated CO2 calibration bottle {bottle_id} median: {median}",
            forward=True)

    def calculate_offset_slope(self) -> None:
        # read true CO2 value for calibration gas bottle
        true_values = []
        measured_values = []

        for key in self.calibration_reading.keys():
            true_value = extract_true_bottle_value(key)

            if true_value is None:
                self.logger.warning(
                    f"Could not find true value for bottle {key} in calibration_cylinders.csv",
                    forward=True)
                return
            else:
                true_values.append(true_value)

            measured_value = self.calibration_reading[key]
            measured_values.append(measured_value)

        # Dynamically determine which value is higher and calculate slope
        if true_values[1] > true_values[0]:
            self.slope = (true_values[1] - true_values[0]) / (
                measured_values[1] - measured_values[0])
            self.offset = true_values[0] - self.slope * measured_values[0]
        else:
            self.slope = (true_values[0] - true_values[1]) / (
                measured_values[0] - measured_values[1])
            self.offset = true_values[1] - self.slope * measured_values[1]

        self.logger.info(
            f"Calculated CO2 calibration slope: {self.slope} and offset: {self.offset}",
            forward=True)

    def send_CO2_measurement_data(
            self, CO2_sensor_data: sensor_types.CO2SensorData) -> None:

        # send out MQTT measurement message
        self.message_queue.enqueue_message(
            timestamp=int(time.time()),
            payload=mqtt_playload_types.MQTTCO2Data(
                gmp343_raw=CO2_sensor_data.raw,
                gmp343_compensated=CO2_sensor_data.compensated,
                gmp343_filtered=CO2_sensor_data.filtered,
                gmp343_temperature=CO2_sensor_data.temperature,
                bme280_temperature=self.air_inlet_bme280_data.temperature,
                bme280_humidity=self.air_inlet_bme280_data.humidity,
                bme280_pressure=self.air_inlet_bme280_data.pressure,
                sht45_temperature=self.air_inlet_sht45_data.temperature,
                sht45_humidity=self.air_inlet_sht45_data.humidity,
            ),
        )

    def send_CO2_calibration_data(self,
                                  CO2_sensor_data: sensor_types.CO2SensorData,
                                  gas_bottle_id: int) -> None:

        # send out MQTT measurement message
        self.message_queue.enqueue_message(
            timestamp=int(time.time()),
            payload=mqtt_playload_types.MQTTCO2CalibrationData(
                cal_bottle_id=float(gas_bottle_id),
                cal_gmp343_raw=CO2_sensor_data.raw,
                cal_gmp343_compensated=CO2_sensor_data.compensated,
                cal_gmp343_filtered=CO2_sensor_data.filtered,
                cal_bme280_temperature=self.air_inlet_bme280_data.temperature,
                cal_bme280_humidity=self.air_inlet_bme280_data.humidity,
                cal_bme280_pressure=self.air_inlet_bme280_data.pressure,
                cal_sht45_temperature=self.air_inlet_sht45_data.temperature,
                cal_sht45_humidity=self.air_inlet_sht45_data.humidity,
                cal_gmp343_temperature=CO2_sensor_data.temperature,
            ),
        )
