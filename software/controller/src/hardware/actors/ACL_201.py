import time
from typing import Literal, Any
import gpiozero

from hardware.actors import base_actor
from custom_types import config_types


class ACLValves(base_actor.Actor):
    """Class for controlling the ACL Type 201 solenoid vales."""

    def __init__(self,
                 config: config_types.Config,
                 pin_factory: gpiozero.pins.pigpio.PiGPIOFactory,
                 max_retries: int = 3,
                 retry_delay: float = 0.5):
        super().__init__(config=config,
                         max_retries=max_retries,
                         retry_delay=retry_delay)

        self.pin_factory = pin_factory
        self.active_input: Literal[1, 2, 3,
                                   4] = self.config.measurement.valve_number

    def _initialize_actor(self) -> None:
        """Initializes the solenoid valves."""

        # initialize device and reserve GPIO pin
        self.valves: dict[Literal[1, 2, 3, 4], gpiozero.OutputDevice] = {
            1:
            gpiozero.OutputDevice(self.config.hardware.valve_power_pin_1_out,
                                  pin_factory=self.pin_factory),
            2:
            gpiozero.OutputDevice(self.config.hardware.valve_power_pin_2_out,
                                  pin_factory=self.pin_factory),
            3:
            gpiozero.OutputDevice(self.config.hardware.valve_power_pin_3_out,
                                  pin_factory=self.pin_factory),
            4:
            gpiozero.OutputDevice(self.config.hardware.valve_power_pin_4_out,
                                  pin_factory=self.pin_factory),
        }

        # Set to sample from main air channel
        self._set(number=self.active_input)

    def _shutdown_actor(self) -> None:
        """Shuts down the solenoid valves."""

        # Reset to sample from main air channel
        self._set(number=self.active_input)

        for valve in self.valves.values():
            # Shut down the device and release all associated resources (such as GPIO pins).
            valve.close()

    def _set(self, *args: Any, **kwargs: Literal[1, 2, 3, 4]) -> None:
        """Sets the state of all solenoid valves
        
        Allows flow through selected valve.
        Permits flow through all other valves.

        Waits shortly after closing input valve 1 before opening calibration
        valves to evacuate the gas volume."""

        number = kwargs.get('number', 1)

        if number == 1:
            self.valves[1].off()
            self.valves[2].off()
            self.valves[3].off()
            self.valves[4].off()
        if number == 2:
            self.valves[1].on()
            self.valves[3].off()
            self.valves[4].off()
            time.sleep(5)
            self.valves[2].on()
        if number == 3:
            self.valves[1].on()
            self.valves[2].off()
            self.valves[4].off()
            time.sleep(5)
            self.valves[3].on()

        if number == 4:
            self.valves[1].on()
            self.valves[2].off()
            self.valves[3].off()
            time.sleep(5)
            self.valves[4].on()

        self.active_input = number
        self.logger.info(f"switched to valve {self.active_input}")
