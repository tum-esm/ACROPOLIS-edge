import os
from typing import TypedDict
import filelock

from interfaces import logging_interface
from custom_types import config_types

from hardware.sensors.vaisala_gmp343 import VaisalaGMP343
from hardware.sensors.vaisala_wxt532 import VaisalaWXT532
from hardware.sensors.bosch_bme280 import BoschBME280
from hardware.sensors.phoenic_contact_UPS import PhoenixContactUPS
from hardware.sensors.sensirion_sht45 import SensirionSHT45
from hardware.sensors.grove_MCP9808 import GroveMCP9808
from hardware.sensors.simcom_sim7600 import SimcomSIM7600

from hardware.actuators.ACL_201 import ACLValves
from hardware.actuators.SP_622_EC_BL import SchwarzerPrecisionPump
from hardware.actuators.heat_box_heater import HeatBoxHeater
from hardware.actuators.heat_box_ventilator import HeatBoxVentilator

from hardware.modules import co2_sensor, wind_sensor, heated_sensor_box

from utils import gpio_pin_factory
from utils.paths import ACROPOLIS_CONTROLLER_LOCKFILE_PATH
from . import communication_queue


class HwLock(TypedDict):
    lock: filelock.FileLock


global_hw_lock: HwLock = {"lock": filelock.FileLock("")}


def acquire_hardware_lock() -> None:
    """make sure that there is only one initialized hardware connection"""
    try:
        global_hw_lock["lock"].acquire()
    except filelock.Timeout:
        raise HardwareInterface.HardwareOccupiedException(
            "hardware occupied by another process")


class HardwareInterface:

    class HardwareOccupiedException(Exception):
        """raise when trying to use the hardware, but it
        is used by another process"""

    def __init__(
            self, config: config_types.Config,
            communication_queue: communication_queue.CommunicationQueue
    ) -> None:
        global_hw_lock["lock"] = filelock.FileLock(
            ACROPOLIS_CONTROLLER_LOCKFILE_PATH,
            timeout=5,
        )
        self.config = config
        self.communication_queue = communication_queue
        self.logger = logging_interface.Logger(
            config=config,
            communication_queue=communication_queue,
            origin="hardware-interface")

        if not self.config.active_components.simulation_mode:
            self.pin_factory = gpio_pin_factory.get_gpio_pin_factory()
        else:
            self.pin_factory = None

        acquire_hardware_lock()

        # measurement sensors
        self.co2_sensor = VaisalaGMP343(
            config=self.config,
            communication_queue=self.communication_queue,
            pin_factory=self.pin_factory)
        self.wind_sensor = VaisalaWXT532(
            config=self.config,
            communication_queue=self.communication_queue,
            pin_factory=self.pin_factory)
        self.ups = PhoenixContactUPS(
            config=self.config,
            communication_queue=self.communication_queue,
            pin_factory=self.pin_factory)
        self.air_inlet_bme280_sensor = BoschBME280(
            config=self.config,
            communication_queue=self.communication_queue,
            variant="air-inlet")
        self.mainboard_sensor = BoschBME280(
            config=self.config,
            communication_queue=self.communication_queue,
            variant="ioboard")
        self.air_inlet_sht45_sensor = SensirionSHT45(
            config=self.config, communication_queue=self.communication_queue)
        self.modem = SimcomSIM7600(
            config=self.config, communication_queue=self.communication_queue)

        if self.config.active_components.run_sensor_heating_control:
            self.heat_box_sensor = GroveMCP9808(
                config=self.config,
                communication_queue=self.communication_queue)

        # measurement actuators
        self.pump = SchwarzerPrecisionPump(
            config=self.config,
            communication_queue=self.communication_queue,
            pin_factory=self.pin_factory)
        self.valves = ACLValves(config=self.config,
                                communication_queue=self.communication_queue,
                                pin_factory=self.pin_factory)

        if self.config.active_components.run_sensor_heating_control:
            self.heat_box_heater = HeatBoxHeater(
                config=self.config,
                communication_queue=self.communication_queue,
                pin_factory=self.pin_factory)
            self.heat_box_ventilator = HeatBoxVentilator(
                config=self.config,
                communication_queue=self.communication_queue,
                pin_factory=self.pin_factory)

        # hardware modules
        self.co2_measurement_module = co2_sensor.CO2MeasurementModule(
            config=config,
            communication_queue=self.communication_queue,
            co2_sensor=self.co2_sensor,
            inlet_bme280=self.air_inlet_bme280_sensor,
            inlet_sht45=self.air_inlet_sht45_sensor)
        self.wind_sensor_module = wind_sensor.WindSensorModule(
            config=config,
            communication_queue=self.communication_queue,
            wind_sensor=self.wind_sensor)

        # modules run as threads
        if self.config.active_components.run_sensor_heating_control:
            self.heating_box_module = heated_sensor_box.HeatingBoxModule(
                config=config,
                communication_queue=self.communication_queue,
                temperature_sensor=self.heat_box_sensor,
                heater=self.heat_box_heater,
                ventilator=self.heat_box_ventilator)
            self.heating_box_module.start()

    def check_errors(self) -> None:
        """checks for detectable hardware errors"""
        self.logger.info("checking for hardware errors")
        self.co2_sensor.check_errors()
        self.wind_sensor.check_errors()

    def teardown(self) -> None:
        """ends all hardware/system connections"""
        self.logger.info("running hardware teardown")

        if not global_hw_lock["lock"].is_locked:
            self.logger.info("not tearing down due to disconnected hardware")
            return

        # threads
        if self.config.active_components.run_sensor_heating_control:
            self.heating_box_module.stop()
            self.heating_box_module.join()

        # measurement sensors
        self.co2_sensor.teardown()
        self.wind_sensor.teardown()
        self.ups.teardown()
        self.air_inlet_bme280_sensor.teardown()
        self.mainboard_sensor.teardown()
        self.air_inlet_sht45_sensor.teardown()
        self.modem.teardown()

        # measurement actors
        self.pump.teardown()
        self.valves.teardown()

        if not self.config.active_components.simulation_mode:
            self.pin_factory.close()

        # release lock
        global_hw_lock["lock"].release()

    def reinitialize(self, config: config_types.Config) -> None:
        """reinitialize all hardware devices"""
        self.config = config
        self.logger.info("running hardware reinitialization")
        acquire_hardware_lock()

        # measurement sensors
        self.co2_sensor.reset_sensor()
        self.wind_sensor.reset_sensor()
        self.ups.reset_sensor()
        self.air_inlet_bme280_sensor.reset_sensor()
        self.mainboard_sensor.reset_sensor()
        self.air_inlet_sht45_sensor.reset_sensor()
        self.modem.reset_sensor()

        # measurement actors
        self.pump.reset_actuator()
        self.valves.reset_actuator()
