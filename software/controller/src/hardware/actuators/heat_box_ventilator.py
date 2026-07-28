from __future__ import annotations
from typing import Any, TYPE_CHECKING
import gpiozero

if TYPE_CHECKING:
    from gpiozero.pins import Factory

from hardware.actuators import _base_actuator
from custom_types import config_types
from interfaces import communication_queue


class HeatBoxVentilator(_base_actuator.Actuator):
    """Class for controlling the heat box ventilator."""

    def __init__(self,
                 config: config_types.Config,
                 communication_queue: communication_queue.CommunicationQueue,
                 pin_factory: Factory | None = None,
                 max_retries: int = 3,
                 retry_delay: float = 0.5):

        super().__init__(config=config,
                         communication_queue=communication_queue,
                         max_retries=max_retries,
                         retry_delay=retry_delay,
                         pin_factory=pin_factory)

    def _initialize_actuator(self) -> None:
        """Initializes the heat box ventilator."""

        self.power_pin = gpiozero.OutputDevice(
            self.config.hardware.heat_box_ventilator_power_pin_out,
            pin_factory=self.pin_factory)

    def _shutdown_actuator(self) -> None:
        """Shuts down the heat box ventilator."""

        if hasattr(
                self,
                "power_pin") and self.power_pin and not self.power_pin.closed:
            self.power_pin.off()
            # Shut down the device and release all associated resources (such as GPIO pins).
            self.power_pin.close()
        else:
            self.logger.warning(
                "Power pin is uninitialized or already closed.")

    def _set(self, *args: Any, **kwargs: bool) -> None:
        """Sets the PWM signal for the heat box ventilator."""

        run_ventilation = kwargs.get('run_ventilation', False)

        if run_ventilation:
            self.power_pin.on()
        else:
            self.power_pin.off()

    def start(self) -> None:
        self._set(run_ventilation=True)

    def stop(self) -> None:
        self._set(run_ventilation=False)
