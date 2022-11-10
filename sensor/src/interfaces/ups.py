import queue
from typing import Literal
import time
from src import utils, types
from src.utils import Constants

try:
    import RPi.GPIO as GPIO

    GPIO.setup(Constants.ups.pin_ready_in, GPIO.IN)
    GPIO.setup(Constants.ups.pin_battery_mode_in, GPIO.IN)
    GPIO.setup(Constants.ups.pin_alarm_in, GPIO.IN)
except (ImportError, RuntimeError):
    pass

log_message_queue: queue.Queue[
    tuple[Literal["info", "warning", "error"], str]
] = queue.Queue()


class UPSInterface:
    def __init__(self, config: types.Config):
        self.logger = utils.Logger(config, "ups")
        for pin, callback in [
            (Constants.ups.pin_ready_in, UPSInterface._interrupt_callback_ready),
            (
                Constants.ups.pin_battery_mode_in,
                UPSInterface._interrupt_callback_battery_mode,
            ),
            (Constants.ups.pin_alarm_in, UPSInterface._interrupt_callback_alarm),
        ]:
            GPIO.add_event_detect(pin, GPIO.BOTH, callback=callback, bouncetime=300)
            callback(pin)

    def write_out_log_message(self) -> None:
        """Write out all log messages generated by GPIO callbacks. This is done
        so that the stream of log messages is synchronous - output the ups logs
        at a certain time in each loop."""
        while True:
            try:
                new_type, new_message = log_message_queue.get_nowait()
                if new_type == "info":
                    self.logger.info(new_message)
                if new_type == "warning":
                    self.logger.warning(new_message)
                if new_type == "error":
                    self.logger.error(new_message)
            except queue.Empty:
                break

    @staticmethod
    def _battery_is_ready() -> bool:
        """The pin goes high if the battery of the UPS is finished loading and
        when the battery voltage is below the threshold set in the UPS software."""
        return GPIO.input(Constants.ups.pin_ready_in) == 1  # type: ignore

    @staticmethod
    def _battery_is_active() -> bool:
        """The pin goes high if the system is powered by the UPS battery."""
        return GPIO.input(Constants.ups.pin_battery_mode_in) == 1  # type: ignore

    @staticmethod
    def _battery_alarm_is_set() -> bool:
        """The pin goes high if the battery has any error or has been disconected."""
        return GPIO.input(Constants.ups.pin_alarm_in) == 1  # type: ignore

    @staticmethod
    def _interrupt_callback_ready(input_pin: int) -> None:
        """Called when battery_is_ready() changes"""
        if UPSInterface._battery_is_ready():

            # check twice whether power is out
            no_power = UPSInterface._battery_is_active()
            time.sleep(1)
            no_power = no_power and UPSInterface._battery_is_active()

            if no_power:
                log_message_queue.put(("error", "battery voltage is under threshold"))
            else:
                log_message_queue.put(("info", "battery is fully charged"))

    @staticmethod
    def _interrupt_callback_battery_mode(input_pin: int) -> None:
        """Called when battery_is_active() changes"""
        if UPSInterface._battery_is_active():
            log_message_queue.put(("warning", "system is powered by battery"))
        else:
            log_message_queue.put(("info", "system is powered externally"))

    @staticmethod
    def _interrupt_callback_alarm(input_pin: int) -> None:
        """Called when battery_alarm_is_set() changes"""
        if GPIO.input(Constants.ups.pin_alarm_in):
            log_message_queue.put(("warning", "battery error detected"))
        else:
            log_message_queue.put(("info", "battery status is ok"))