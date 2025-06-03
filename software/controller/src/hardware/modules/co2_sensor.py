from typing import Any, Dict, Optional

from custom_types import config_types, sensor_types, mqtt_playload_types
from interfaces import logging_interface, communication_queue
from utils import ring_buffer, athmospheric_conversion
from utils.extract_true_bottle_value import extract_true_bottle_value
from hardware.sensors.vaisala_gmp343 import VaisalaGMP343
from hardware.sensors.bosch_bme280 import BoschBME280
from hardware.sensors.sensirion_sht45 import SensirionSHT45
from interfaces import state_interface


class CO2MeasurementModule:
    """Combines sensor and actor interfaces."""

    def __init__(self, config: config_types.Config,
                 communication_queue: communication_queue.CommunicationQueue,
                 co2_sensor: VaisalaGMP343, inlet_bme280: BoschBME280,
                 inlet_sht45: SensirionSHT45) -> None:

        self.logger = logging_interface.Logger(
            config=config,
            communication_queue=communication_queue,
            origin="CO2MeasurementModule")
        self.config = config
        self.communication_queue = communication_queue
        self.reset_ring_buffers()
        self.calibration_reading: Dict[Any, Any] = {}

        # read slope and offset from state file
        state = state_interface.StateInterface.read(
            config=self.config, communication_queue=self.communication_queue)
        self.slope = state.co2_sensor_slope
        self.intercept = state.co2_sensor_intercept

        # hardware
        self.co2_sensor = co2_sensor
        self.inlet_bme280 = inlet_bme280
        self.inlet_sht45 = inlet_sht45
        self._update_air_inlet_parameters()

    def perform_CO2_measurement(self, calibration_mode: bool = False) -> Any:
        """do regular measurements for in config defined measurement interval"""

        # Get latest auxiliary sensor data information
        self._update_air_inlet_parameters()

        if not calibration_mode:
            humidity = self.rb_humidity.avg()
        else:
            humidity = 0.0

        # perform a CO2 measurement
        CO2_sensor_data = (self.co2_sensor.read_with_retry(
            timeout=60,
            pressure=self.rb_pressure.avg(),
            humidity=humidity,
        ))
        self.logger.debug(f"new measurement: {CO2_sensor_data}")

        # send health check after successful measurement
        self.communication_queue.enqueue_health_check()

        return CO2_sensor_data

    def perform_edge_correction(
            self, CO2_sensor_data: sensor_types.CO2SensorData
    ) -> tuple[float, float]:
        """Performs wet -> dry conversion and calibration correction and returns corrected CO2 value"""

        # Apply wet -> dry conversion
        co2_dry = athmospheric_conversion.calculate_co2dry(
            co2wet=CO2_sensor_data.filtered,
            temperature=CO2_sensor_data.temperature,
            rh=self.rb_humidity.avg(),
            pressure=self.rb_pressure.avg() * 100,
        )

        # Apply calibration slope and offset
        co2_corrected = self.slope * co2_dry + self.intercept

        return round(co2_dry, 1), round(co2_corrected, 1)

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

    def calculate_intercept_slope(self) -> None:
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
            slope = (true_values[1] - true_values[0]) / (measured_values[1] -
                                                         measured_values[0])
            intercept = true_values[0] - slope * measured_values[0]
        else:
            slope = (true_values[0] - true_values[1]) / (measured_values[0] -
                                                         measured_values[1])
            intercept = true_values[1] - slope * measured_values[1]

        # check validity of slope and intercept
        state = state_interface.StateInterface.read(
            config=self.config, communication_queue=self.communication_queue)

        if not (state.co2_sensor_slope * 0.9 < slope <
                state.co2_sensor_slope * 1.1):
            self.logger.warning(
                f"Calculated CO2 calibration slope: {slope} is not within 10% of previous value: {state.co2_sensor_slope}.",
                forward=True)
            self.logger.warning(
                f"Calibration might have failed. Calibration results will be discarded.",
                forward=True)
            return

        # update slope and intercept
        self.slope, self.intercept = slope, intercept
        state.co2_sensor_slope, state.co2_sensor_intercept = slope, intercept
        # persist slope and offset to state file
        state_interface.StateInterface.write(state)
        self.logger.info(
            f"Calculated CO2 calibration slope: {self.slope} and intercept: {self.intercept}",
            forward=True)

    def send_CO2_measurement_data(
            self,
            CO2_sensor_data: sensor_types.CO2SensorData,
            edge_dry: Optional[float] = None,
            edge_corrected: Optional[float] = None) -> None:

        # do not send out measurements if they are not valid
        if CO2_sensor_data.raw == 0.0:
            self.logger.debug(
                "CO2 raw value is 0.0, not sending measurement data.")

        # send out MQTT measurement message
        self.communication_queue.enqueue_message(
            type="measurement",
            payload=mqtt_playload_types.MQTTCO2Data(
                gmp343_raw=CO2_sensor_data.raw,
                gmp343_compensated=CO2_sensor_data.compensated,
                gmp343_filtered=CO2_sensor_data.filtered,
                gmp343_temperature=CO2_sensor_data.temperature,
                gmp343_edge_dry=edge_dry,
                gmp343_edge_corrected=edge_corrected,
                bme280_temperature=self.air_inlet_bme280_data.temperature,
                bme280_humidity=self.air_inlet_bme280_data.humidity,
                bme280_pressure=self.air_inlet_bme280_data.pressure,
                sht45_temperature=self.air_inlet_sht45_data.temperature,
                sht45_humidity=self.air_inlet_sht45_data.humidity,
            ), )

    def send_CO2_calibration_data(self,
                                  CO2_sensor_data: sensor_types.CO2SensorData,
                                  gas_bottle_id: int) -> None:

        # send out MQTT measurement message
        self.communication_queue.enqueue_message(
            type="measurement",
            payload=mqtt_playload_types.MQTTCO2CalibrationData(
                cal_bottle_id=gas_bottle_id,
                cal_gmp343_raw=CO2_sensor_data.raw,
                cal_gmp343_compensated=CO2_sensor_data.compensated,
                cal_gmp343_filtered=CO2_sensor_data.filtered,
                cal_bme280_temperature=self.air_inlet_bme280_data.temperature,
                cal_bme280_humidity=self.air_inlet_bme280_data.humidity,
                cal_bme280_pressure=self.air_inlet_bme280_data.pressure,
                cal_sht45_temperature=self.air_inlet_sht45_data.temperature,
                cal_sht45_humidity=self.air_inlet_sht45_data.humidity,
                cal_gmp343_temperature=CO2_sensor_data.temperature,
            ), )

    def send_calibration_correction_data(self) -> None:

        # send out MQTT measurement message
        self.communication_queue.enqueue_message(
            type="measurement",
            payload=mqtt_playload_types.MQTTCalibrationCorrectionData(
                cal_gmp343_slope=round(self.slope, 4),
                cal_gmp343_intercept=round(self.intercept, 2),
                cal_sht_45_offset=self.inlet_sht45.humidity_offset), )
