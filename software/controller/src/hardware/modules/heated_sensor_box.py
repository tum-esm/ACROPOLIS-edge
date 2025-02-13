import time
import threading
from datetime import datetime, timezone
try:
    from simple_pid import PID
except Exception:
    pass

from custom_types import config_types
from interfaces import logging_interface
from utils import message_queue
from hardware.sensors.grove_MCP9808 import GroveMCP9808
from hardware.actuators.heat_box_heater import HeatBoxHeater
from hardware.actuators.heat_box_ventilator import HeatBoxVentilator


class HeatingBoxModule(threading.Thread):
    """Combines sensor and actor interfaces and runs as a thread."""

    def __init__(self, config: config_types.Config,
                 temperature_sensor: GroveMCP9808, heater: HeatBoxHeater,
                 ventilator: HeatBoxVentilator) -> None:
        super().__init__()
        self.logger = logging_interface.Logger(config=config,
                                               origin="HeatingBoxModule")
        self.config = config
        self.message_queue = message_queue.MessageQueue()

        # hardware
        self.temperature_sensor = temperature_sensor
        self.heater = heater
        self.ventilator = ventilator

        # pid
        self.pid = PID(1, 0.1, 0.05, setpoint=40)
        self.pid.output_limits = (0, 1)

        # default actor values
        self.heater.set(pwm_duty_cycle=0)
        self.ventilator.start()

        self._stop_event = threading.Event()

    def run(self) -> None:
        """Runs the PID control loop for temperature in a separate thread."""
        try:
            last_log_timestamp = 0.0

            while not self._stop_event.is_set():
                temp = self.temperature_sensor.read_with_retry()
                assert isinstance(temp,
                                  float), "Temperature should be a float."

                control = self.pid(temp)
                self.heater.set(pwm_duty_cycle=control)

                if time.time() - last_log_timestamp > 5:
                    self.logger.info(
                        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}: "
                        f"Temperature: {round(temp, 2)}, Control: {control}")
                    last_log_timestamp = time.time()

                time.sleep(0.1)
        except Exception as e:
            self.logger.error(
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}: Error - {e}"
            )
        finally:
            self.teardown()
            self.logger.info(
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}: Heater and ventilation powered off."
            )

    def stop(self) -> None:
        """Stops the thread by setting the stop event."""
        self._stop_event.set()

    def teardown(self) -> None:
        """Set default actor values."""
        self.heater.set(pwm_duty_cycle=0)
        self.ventilator.stop()
