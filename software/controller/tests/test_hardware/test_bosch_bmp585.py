import pytest
from hardware.sensors.bosch_bmp585 import decode_measurement


@pytest.mark.github_action
def test_decode_measurement():
    """25.5 °C and 1013.25 hPa, little-endian 24-bit raw values."""
    temperature_raw = int(25.5 * 2**16).to_bytes(3, "little")
    pressure_raw = int(101325 * 2**6).to_bytes(3, "little")
    assert decode_measurement(list(temperature_raw + pressure_raw)) == (
        25.5, 1013.25)


@pytest.mark.github_action
def test_decode_negative_temperature():
    temperature_raw = (-int(10 * 2**16) & 0xFFFFFF).to_bytes(3, "little")
    assert decode_measurement(list(temperature_raw + bytes(3)))[0] == -10
