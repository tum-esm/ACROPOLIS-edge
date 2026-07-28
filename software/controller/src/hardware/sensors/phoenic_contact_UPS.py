
from __future__ import annotations
from typing import Any, TYPE_CHECKING
import gpiozero

if TYPE_CHECKING:
    from gpiozero.pins import Factory

from hardware.sensors._base_sensor import Sensor
from custom_types import config_types, sensor_types
from interfaces import communication_queue


class PhoenixContactUPS(Sensor):
    """Class for the Phoenix Contact Trio-UPS-2G."""

    def __init__(self, config: config_types.Config,
                 communication_queue: communication_queue.CommunicationQueue,
                 pin_factory: Factory,) -> None:
        super().__init__(config=config,
                         communication_queue=communication_queue,
                         pin_factory=pin_factory)

    def _initialize_sensor(self) -> None:
        """Initialize the sensor."""

        self.pins: dict[str, gpiozero.DigitalInputDevice] = {
            "UPS_BATTERY_CHARGE_PIN_IN":
            gpiozero.DigitalInputDevice(
                self.config.hardware.ups_battery_charge_pin_in,
                bounce_time=0.3,
                pin_factory=self.pin_factory,
            ),
            "UPS_POWER_MODE_PIN_IN":
            gpiozero.DigitalInputDevice(
                self.config.hardware.ups_power_mode_pin_in,
                bounce_time=0.3,
                pin_factory=self.pin_factory,
            ),
            "UPS_ALARM_PIN_IN":
            gpiozero.DigitalInputDevice(
                self.config.hardware.ups_alarm_pin_in,
                bounce_time=0.3,
                pin_factory=self.pin_factory,
            )
        }

    def _shutdown_sensor(self) -> None:
        """Shutdown the sensor."""

        for pin in self.pins.values():

            if pin and not pin.closed:
                # Shut down the device and release all associated resources (such as GPIO pins).
                pin.close()
            else:
                self.logger.warning(
                    "Power pin is uninitialized or already closed.")

    def _read(self, *args: Any, **kwargs: Any) -> sensor_types.UPSSensorData:
        """Read the sensor value."""

        ups_powered_by_grid = self._read_power_mode()
        battery_is_fully_charged = self._read_battery_charge_state()
        battery_error_detected = self._read_alarm_state()
        battery_above_voltage_threshold = self._read_voltage_threshold_state()

        return sensor_types.UPSSensorData(
            ups_powered_by_grid=ups_powered_by_grid,
            ups_battery_is_fully_charged=battery_is_fully_charged,
            ups_battery_error_detected=battery_error_detected,
            ups_battery_above_voltage_threshold=battery_above_voltage_threshold
        )

    def _simulate_read(self, *args: Any,
                       **kwargs: Any) -> sensor_types.UPSSensorData:
        """Simulate the sensor value."""
        return sensor_types.UPSSensorData(
            ups_powered_by_grid=True,
            ups_battery_is_fully_charged=True,
            ups_battery_error_detected=False,
            ups_battery_above_voltage_threshold=True)

    def _read_power_mode(self) -> bool:
        """
        UPS_POWER_MODE_PIN_IN is HIGH when the system is powered by the battery
        UPS_POWER_MODE_PIN_IN is LOW when the system is powered by the grid
        """

        if self.pins["UPS_POWER_MODE_PIN_IN"].is_active:
            self.logger.info("System is powered by the battery")
            return False
        else:
            self.logger.info("System is powered by the grid")
            return True

    def _read_battery_charge_state(self) -> bool:
        """
        UPS_BATTERY_CHARGE_PIN_IN is HIGH when the battery is fully charged
        UPS_BATTERY_CHARGE_PIN_IN is LOW when the battery is not fully charged
        """

        if self.pins["UPS_BATTERY_CHARGE_PIN_IN"].is_active:
            self.logger.info("The battery is fully charged")
            return True
        else:
            self.logger.info("The battery is not fully charged")
            return False

    def _read_alarm_state(self) -> bool:
        """
        UPS_ALARM_PIN_IN is HIGH when a battery error is detected
        UPS_ALARM_PIN_IN is LOW when the battery status is okay"
        """

        if self.pins["UPS_ALARM_PIN_IN"].is_active:
            self.logger.info("A battery error was detected")
            return True
        else:
            self.logger.info("The battery status is fine")
            return False

    def _read_voltage_threshold_state(self) -> bool:
        """When UPS_BATTERY_CHARGE_PIN_IN is HIGH & UPS_POWER_MODE_PIN_IN is HIGH
        the battery voltage has dropped below the minimum threshold.
        """

        if self.pins["UPS_BATTERY_CHARGE_PIN_IN"].is_active & self.pins[
                "UPS_POWER_MODE_PIN_IN"].is_active:
            self.logger.info(
                "The battery voltage has dropped below the minimum threshold")
            return False
        else:
            self.logger.info(
                "The battery voltage is above the minimum threshold")
            return True
