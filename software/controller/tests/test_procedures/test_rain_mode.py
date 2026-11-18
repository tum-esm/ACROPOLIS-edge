from custom_types.config_types import RainModeConfig
from procedures.rain_mode import RainMode


def test_pauses_after_wet_period_and_resumes_after_dry_period():
    mode = RainMode(RainModeConfig())
    assert not mode.update(60, now=0)
    assert not mode.update(45, now=300)      # short spike resets the timer
    assert not mode.update(60, now=400)
    assert mode.update(60, now=1000)         # 600 s above 50 %
    assert mode.update(45, now=2000)         # between thresholds: stays paused
    assert mode.update(35, now=2100)
    assert not mode.update(35, now=3900)     # 1800 s below 40 %


def test_resumes_after_max_pause():
    mode = RainMode(RainModeConfig(max_pause_seconds=3600))
    mode.update(90, now=0)
    assert mode.update(90, now=600)
    assert not mode.update(90, now=4200)
