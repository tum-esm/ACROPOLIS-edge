import time
from typing import Optional

from custom_types import config_types
from interfaces import hardware_interface, logging_interface, communication_queue

RECHECK_SECONDS = 60


class RainMode:
    """Decides from the air-inlet humidity whether pumping pauses.

    Pauses after the humidity stays above `stop_above_percent` for
    `stop_after_seconds`. Resumes after it stays below `resume_below_percent`
    for `resume_after_seconds`, or after `max_pause_seconds` at the latest."""

    def __init__(self, config: config_types.RainModeConfig) -> None:
        self.config = config
        self.paused = False
        self.paused_since: Optional[float] = None
        self.wet_since: Optional[float] = None
        self.dry_since: Optional[float] = None

    def update(self, humidity: float, now: float) -> bool:
        """Returns True while pumping should pause. `now` is in seconds."""
        if not self.paused:
            self.wet_since = (now if self.wet_since is None else self.wet_since) if humidity > self.config.stop_above_percent else None
            if self.wet_since is not None and now - self.wet_since >= self.config.stop_after_seconds:
                self.paused, self.paused_since, self.dry_since = True, now, None
            return self.paused

        self.dry_since = (now if self.dry_since is None else self.dry_since) if humidity < self.config.resume_below_percent else None
        dried = self.dry_since is not None and now - self.dry_since >= self.config.resume_after_seconds
        assert self.paused_since is not None  # set whenever paused
        timed_out = now - self.paused_since >= self.config.max_pause_seconds
        if dried or timed_out:
            self.paused, self.paused_since, self.wet_since = False, None, None
        return self.paused


class RainModeProcedure:
    """runs every mainloop call before calibration and measurement

    Stops the pump while the air inlet is wet, restarts it once dry.
    Off when the config has no `rain_mode` block."""

    def __init__(
            self, config: config_types.Config,
            communication_queue: communication_queue.CommunicationQueue,
            hardware_interface: hardware_interface.HardwareInterface) -> None:
        self.logger, self.config = logging_interface.Logger(
            config=config,
            communication_queue=communication_queue,
            origin="rain-mode-procedure"), config
        self.hardware_interface = hardware_interface
        self.rain_mode = RainMode(config.rain_mode) if config.rain_mode else None

    def run(self) -> bool:
        """Returns True while paused: skip calibration and measurement."""
        if self.rain_mode is None:
            return False

        humidity = self.hardware_interface.air_inlet_sht45_sensor.read().humidity
        was_paused = self.rain_mode.paused
        paused = self.rain_mode.update(humidity, time.time())

        if paused and not was_paused:
            self.logger.warning(f"Rain mode on: air-inlet humidity {humidity:.1f} %, pump stopped.", forward=True)
            self.hardware_interface.pump.set(pwm_duty_cycle=0)
        elif was_paused and not paused:
            self.logger.info(f"Rain mode off: air-inlet humidity {humidity:.1f} %, pump restarted.", forward=True)
            self.hardware_interface.pump.set(pwm_duty_cycle=self.config.hardware.pump_pwm_duty_cycle)

        if paused:
            time.sleep(RECHECK_SECONDS)
        return paused
