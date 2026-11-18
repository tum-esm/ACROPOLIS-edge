from custom_types.config_types import RainModeConfig
from procedures.rain_mode import RainMode


def test_pauses_when_wet_and_tests_again_after_pause():
    mode = RainMode(RainModeConfig())
    mode.check(45, now=0)
    assert not mode.paused
    mode.check(60, now=0)
    assert mode.paused and not mode.test_run_due(3599) and mode.test_run_due(3600)


def test_test_run_decides():
    mode = RainMode(RainModeConfig())
    mode.check(60, now=0)
    mode.check(60, now=3660)                 # still wet: another hour
    assert mode.paused and not mode.test_run_due(3660 + 3599)
    mode.check(45, now=7320)                 # dry: measure again
    assert not mode.paused
