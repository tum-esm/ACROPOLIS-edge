import statistics
import time
from typing import Optional

from custom_types import config_types, mqtt_playload_types
from interfaces import hardware_interface, logging_interface, communication_queue

RECHECK_SECONDS = 60
TEST_RUN_SAMPLE_SECONDS = 10


class RainMode:
    """Pause state of the pump while the air inlet is wet.

    Wet (humidity above `stop_above_percent`): pause for `pause_seconds`.
    Then a test run pumps for `test_pump_seconds` and checks again:
    still wet pauses again, dry resumes."""

    def __init__(self, config: config_types.RainModeConfig) -> None:
        self.config = config
        self.paused_until: Optional[float] = None

    @property
    def paused(self) -> bool:
        return self.paused_until is not None

    def is_wet(self, humidity: float) -> bool:
        return humidity > self.config.stop_above_percent

    def test_run_due(self, now: float) -> bool:
        return self.paused_until is not None and now >= self.paused_until

    def check(self, humidity: float, now: float) -> None:
        self.paused_until = now + self.config.pause_seconds if self.is_wet(humidity) else None


class RainModeProcedure:
    """runs every mainloop call before calibration and measurement

    On by default; off with `rain_mode.enabled = false`."""

    def __init__(
            self, config: config_types.Config,
            communication_queue: communication_queue.CommunicationQueue,
            hardware_interface: hardware_interface.HardwareInterface) -> None:

        self.logger, self.config = logging_interface.Logger(
            config=config,
            communication_queue=communication_queue,
            origin="rain-mode-procedure"), config
        self.hardware_interface = hardware_interface
        self.communication_queue = communication_queue
        self.rain_mode = RainMode(config.rain_mode)

    @property
    def enabled(self) -> bool:
        return self.config.rain_mode.enabled

    @property
    def paused(self) -> bool:
        return self.rain_mode.paused

    def run(self) -> None:
        """Pauses the pump while the inlet is wet; test run after each pause."""
        if self.rain_mode.paused and not self.rain_mode.test_run_due(time.time()):
            self._send_state()
            time.sleep(RECHECK_SECONDS)
            return

        was_paused = self.rain_mode.paused
        humidity = self._test_run() if was_paused else self._recent_humidity()
        self.rain_mode.check(humidity, time.time())

        if self.rain_mode.paused:
            self.logger.warning(
                f"Rain mode on: air-inlet humidity {humidity:.1f} %, pump off for {self.config.rain_mode.pause_seconds} s.",
                forward=True)
            self._set_pump(on=False)
        elif was_paused:
            self.logger.info(f"Rain mode off: air-inlet humidity {humidity:.1f} %, measuring again.", forward=True)
            # drop the wet readings from before the pause, otherwise the next check pauses again
            self.hardware_interface.co2_measurement_module.rb_humidity.clear()
        self._send_state()

    def _recent_humidity(self) -> float:
        """Median of the inlet humidity over the last measurement interval (about 2.5 min)."""
        median = self.hardware_interface.co2_measurement_module.rb_humidity.median()
        if median is None:
            return float(self.hardware_interface.air_inlet_sht45_sensor.read().humidity)
        return float(median)

    def _test_run(self) -> float:
        """Pumps for `test_pump_seconds`; median humidity of the second half (fresh air)."""
        self.logger.info(f"Rain mode: test run, pumping {self.config.rain_mode.test_pump_seconds} s.")
        self._set_pump(on=True)
        readings = []
        start = time.time()
        while time.time() - start < self.config.rain_mode.test_pump_seconds:
            time.sleep(TEST_RUN_SAMPLE_SECONDS)
            readings.append(self.hardware_interface.air_inlet_sht45_sensor.read().humidity)
        return float(statistics.median(readings[len(readings) // 2:]))

    def _set_pump(self, on: bool) -> None:
        duty_cycle = self.config.hardware.pump_pwm_duty_cycle if on else 0
        self.hardware_interface.pump.set(pwm_duty_cycle=duty_cycle)

    def _send_state(self) -> None:
        self.communication_queue.enqueue_message(
            type="measurement",
            payload=mqtt_playload_types.MQTTRainModeData(rain_mode_paused=int(self.rain_mode.paused)))
