from __future__ import annotations
import time
from typing import Any, TYPE_CHECKING
try:
    import gpiozero
    import gpiozero.pins.pigpio
except Exception:
    pass

if TYPE_CHECKING:
    from gpiozero.pins import Factory

from hardware.actuators import _base_actuator
from custom_types import config_types
from interfaces import communication_queue


class SchwarzerPrecisionPump(_base_actuator.Actuator):
    """Class for controlling the SP 622 EC_BL membrane pump."""

    def __init__(
        self,
        config: config_types.Config,
        communication_queue: communication_queue.CommunicationQueue,
        pin_factory: Factory | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ):
        # Ensure default_pwm_duty_cycle is set before base class initialization
        self.default_pwm_duty_cycle = config.hardware.pump_pwm_duty_cycle

        super().__init__(config=config,
                         communication_queue=communication_queue,
                         max_retries=max_retries,
                         retry_delay=retry_delay,
                         pin_factory=pin_factory)

    def _initialize_actuator(self) -> None:
        """Initializes the membrane pump."""

        # initialize device and reserve GPIO pin
        self.power_pin = gpiozero.PWMOutputDevice(
            pin=self.config.hardware.pump_power_pin_out,
            active_high=True,
            initial_value=False,
            frequency=self.config.hardware.pump_power_pin_frequency,
            pin_factory=self.pin_factory,
        )

        # start pump to run continuously
        self.set(pwm_duty_cycle=self.default_pwm_duty_cycle)

    def _shutdown_actuator(self) -> None:
        """Shuts down the membrane pump."""

        if hasattr(
                self,
                "power_pin") and self.power_pin and not self.power_pin.closed:
            self.power_pin.off()
            # Shut down the device and release all associated resources (such as GPIO pins).
            self.power_pin.close()
        else:
            self.logger.warning(
                "Power pin is uninitialized or already closed.")

    def _set(self, *args: Any, **kwargs: float) -> None:
        """Sets the PWM signal for the pump."""

        pwm_duty_cycle = kwargs.get('pwm_duty_cycle',
                                    self.default_pwm_duty_cycle)

        assert (
            0 <= pwm_duty_cycle <= 1
        ), f"pwm duty cycle has to be between 0 and 1 (passed {pwm_duty_cycle})"
        self.power_pin.value = pwm_duty_cycle

    def flush_system(self, duration: int, pwm_duty_cycle: float) -> None:
        """Flushes the system with the pump for a given duration and duty cycle."""
        assert (
            0 <= pwm_duty_cycle <= 1
        ), f"pwm duty cycle has to be between 0 and 1 (passed {pwm_duty_cycle})"

        self.set(pwm_duty_cycle=pwm_duty_cycle)
        time.sleep(duration)
        self.set(pwm_duty_cycle=self.default_pwm_duty_cycle)
