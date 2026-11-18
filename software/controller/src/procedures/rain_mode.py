from custom_types import config_types


class RainMode:
    """Decides from the air-inlet humidity whether pumping pauses.

    Pauses after the humidity stays above `stop_above_percent` for
    `stop_after_seconds`. Resumes after it stays below `resume_below_percent`
    for `resume_after_seconds`, or after `max_pause_seconds` at the latest."""

    def __init__(self, config: config_types.RainModeConfig) -> None:
        self.config = config
        self.paused = False
        self.paused_since: float | None = None
        self.wet_since: float | None = None
        self.dry_since: float | None = None

    def update(self, humidity: float, now: float) -> bool:
        """Returns True while pumping should pause. `now` is in seconds."""
        if not self.paused:
            self.wet_since = (now if self.wet_since is None else self.wet_since) if humidity > self.config.stop_above_percent else None
            if self.wet_since is not None and now - self.wet_since >= self.config.stop_after_seconds:
                self.paused, self.paused_since, self.dry_since = True, now, None
            return self.paused

        self.dry_since = (now if self.dry_since is None else self.dry_since) if humidity < self.config.resume_below_percent else None
        dried = self.dry_since is not None and now - self.dry_since >= self.config.resume_after_seconds
        timed_out = now - self.paused_since >= self.config.max_pause_seconds
        if dried or timed_out:
            self.paused, self.paused_since, self.wet_since = False, None, None
        return self.paused
