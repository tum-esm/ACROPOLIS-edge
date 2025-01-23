import time
from datetime import datetime
import pytz

from custom_types import config_types
from interfaces import logging_interface, state_interface, hardware_interface
from utils import message_queue, ring_buffer


class CalibrationProcedure:
    """runs when a calibration is due"""

    def __init__(
            self, config: config_types.Config,
            hardware_interface: hardware_interface.HardwareInterface) -> None:
        self.logger, self.config = logging_interface.Logger(
            config=config, origin="calibration-procedure"), config
        self.hardware_interface = hardware_interface

        self.last_measurement_time: float = 0
        self.message_queue = message_queue.MessageQueue()
        self.seconds_drying_with_first_bottle = 0

    def run(self) -> None:
        state = state_interface.StateInterface.read(config=self.config)
        calibration_time = datetime.now().timestamp()
        self.logger.info(
            "starting calibration procedure",
            forward=True,
        )

        # save last calibration attempt to only trigger calibrate procedure once a day
        # if the calibration fails it will be triggered again the next day
        self.logger.debug("updating state")

        state = state_interface.StateInterface.read(config=self.config)
        state.last_calibration_attempt = calibration_time
        state_interface.StateInterface.write(state)

        # alternate calibration bottle order every other day
        # first bottle receives additional time to dry air chamber
        sequence_calibration_bottle = self._alternate_bottle_for_drying()

        for gas in sequence_calibration_bottle:

            # clear ring buffers
            self.hardware_interface.co2_measurement_module.reset_ring_buffers()

            self.logger.info(
                f"Switching to calibration gas bottle ID: {gas.bottle_id} Valve: {gas.valve_number}",
                forward=True)

            # switch to each calibration valve
            self.hardware_interface.valves.set(number=gas.valve_number)

            self._co2_measurement_interval(gas=gas.valve_number)

            # reset drying time extension for following bottles
            self.seconds_drying_with_first_bottle = 0

        # perform calibration corrections
        if self.config.active_components.perform_sht45_offset_correction:
            self.calibrate_sht45_zero_point()

        if self.config.active_components.perform_co2_calibration_correction:
            self.hardware_interface.co2_measurement_module.calculate_offset_slope(
            )

        # switch back to measurement inlet
        self.hardware_interface.valves.set(
            number=self.config.measurement.valve_number)

        # flush the system after calibration at max pump speed
        self.hardware_interface.pump.flush_system(
            duration=self.config.calibration.system_flushing_seconds,
            pwm_duty_cycle=self.config.calibration.
            system_flushing_pump_pwm_duty_cycle,
        )

        # clear ring buffers
        self.hardware_interface.co2_measurement_module.reset_ring_buffers()

        self.logger.info(
            f"finished calibration procedure",
            forward=True,
        )

    def is_due(self) -> bool:
        """returns true when calibration procedure should run

        two conditions are checked:
        1. time > last calibration day + x days (config) at time (config)
        2. day of last calibration was not today
        #"""

        # load state, kept during configuration procedures
        state = state_interface.StateInterface.read(config=self.config)

        current_local_time = datetime.now().astimezone(
            pytz.timezone(self.config.local_time_zone))
        current_local_date = current_local_time.date()
        current_local_hour = current_local_time.hour

        # skip calibration when sensor has had power for less than 30
        # minutes (a full warming up is required for maximum accuracy)
        seconds_since_last_co2_sensor_boot = round(
            time.time() - self.hardware_interface.co2_sensor.last_powerup_time)

        if seconds_since_last_co2_sensor_boot < 1800:
            self.logger.info(
                f"skipping calibration, sensor is still warming up (co2 sensor"
                f" booted {seconds_since_last_co2_sensor_boot} seconds ago)")
            return False

        # if last calibration time is unknown, calibrate now
        # only happens when the state.json is recreated
        if state.last_calibration_attempt is None:
            self.logger.info(
                "last calibration time is unknown, calibrating now")
            return True

        # check if a calibration was already performed on the same day
        last_calibration_date = datetime.fromtimestamp(
            state.last_calibration_attempt).date()

        if current_local_date == last_calibration_date:
            self.logger.info("last calibration was already done today")
            return False

        # compare scheduled calibration day to today
        days_since_last_calibration = (current_local_date -
                                       last_calibration_date).days

        if days_since_last_calibration < self.config.calibration.calibration_frequency_days:
            self.logger.info(f"next scheduled calibration is not due today.")
            return False

        # check if current hour is past the scheduled hour of day
        if current_local_hour < self.config.calibration.calibration_hour_of_day:
            self.logger.info("next calibration is scheduled for later today")
            return False

        self.logger.info("next calibration is due, calibrating now")
        return True

    def _co2_measurement_interval(self, gas: int) -> None:
        calibration_procedure_start_time = time.time()
        while True:
            # idle until next measurement period
            seconds_to_wait_for_next_measurement = max(
                self.config.hardware.gmp343_filter_seconds_averaging -
                (time.time() - self.last_measurement_time),
                0,
            )
            self.logger.debug(
                f"sleeping {round(seconds_to_wait_for_next_measurement, 3)} seconds"
            )
            time.sleep(seconds_to_wait_for_next_measurement)
            self.last_measurement_time = time.time()

            # perform measurement
            measurement = self.hardware_interface.co2_measurement_module.perform_CO2_measurement(
            )
            # send measurement
            self.hardware_interface.co2_measurement_module.send_CO2_calibration_data(
                CO2_sensor_data=measurement, gas_bottle_id=gas)

            # log measurements for local calibration correction
            self.hardware_interface.co2_measurement_module.calibration_co2_buffer.append(
                measurement.filtered)

            if ((self.last_measurement_time - calibration_procedure_start_time)
                    >= self.config.calibration.sampling_per_cylinder_seconds +
                    self.seconds_drying_with_first_bottle):

                # log calibration median
                median = self.hardware_interface.co2_measurement_module.calibration_co2_buffer.calculate_calibration_median(
                )
                self.hardware_interface.co2_measurement_module.log_cylinder_median(
                    bottle_id=gas, median=median)
                break

    def _alternate_bottle_for_drying(
            self) -> list[config_types.CalibrationGasConfig]:
        """
        1. sets time for drying the air chamber with first calibration bottle
        2. switches to the next calibration cylinder every other calibration
        """

        # set time extension for first bottle
        self.seconds_drying_with_first_bottle = (
            self.config.calibration.sampling_per_cylinder_seconds)

        # read the latest state
        state = state_interface.StateInterface.read(config=self.config)

        current_position = state.next_calibration_cylinder

        if current_position + 1 < len(self.config.calibration.gas_cylinders):
            next_position = current_position + 1
        else:
            next_position = 0

        # update state config
        state.next_calibration_cylinder = next_position
        state_interface.StateInterface.write(state)

        # update sequence

        # 2 calibration cylinders
        if len(self.config.calibration.gas_cylinders) == 2:
            if current_position == 0:
                return self.config.calibration.gas_cylinders
            if current_position == 1:
                return [
                    self.config.calibration.gas_cylinders[1],
                    self.config.calibration.gas_cylinders[0],
                ]

        # 3 calibration cylinders
        if len(self.config.calibration.gas_cylinders) == 3:
            if current_position == 0:
                return self.config.calibration.gas_cylinders
            if current_position == 1:
                return [
                    self.config.calibration.gas_cylinders[1],
                    self.config.calibration.gas_cylinders[2],
                    self.config.calibration.gas_cylinders[0],
                ]
            if current_position == 2:
                return [
                    self.config.calibration.gas_cylinders[2],
                    self.config.calibration.gas_cylinders[1],
                    self.config.calibration.gas_cylinders[0],
                ]

        # 1 or 4+ calibration cylinders
        return self.config.calibration.gas_cylinders

    def calibrate_sht45_zero_point(self) -> None:
        """determines the humidity offset for the SHT45 sensor by measuring
        the calibration tanks for a configured time. The offset is calculated by
        the median of the last 60 measurements"""

        self.logger.info("Calibrating SHT45 humidity offset", forward=True)
        self.hardware_interface.air_inlet_sht45_sensor.set_humidity_offset(0.0)
        duration = self.config.calibration.sht45_calibration_seconds

        sht45_ring_buffer = ring_buffer.RingBuffer(size=duration)
        calibration_start_time = time.time()
        while (True):
            measurement = self.hardware_interface.air_inlet_sht45_sensor.read()

            sht45_ring_buffer.append(measurement.humidity)

            if (time.time() - calibration_start_time) >= duration:
                break

            time.sleep(1)

        # rh offsets is calculated from median of humidity readings of last calibration bottle
        rh_offset = self.hardware_interface.co2_measurement_module.rb_humidity.median(
        )
        self.hardware_interface.air_inlet_sht45_sensor.set_humidity_offset(
            rh_offset)

        # persist humidity offset in state file
        state = state_interface.StateInterface.read(config=self.config)
        state.sht45_humidity_offset = rh_offset
        state_interface.StateInterface.write(state)

        self.logger.info(f"STH45 humidity offset: {rh_offset}", forward=True)
