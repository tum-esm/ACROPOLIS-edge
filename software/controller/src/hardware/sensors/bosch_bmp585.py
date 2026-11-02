import time
import random
from typing import Any

try:
    import smbus2
except ImportError:
    pass

from hardware.sensors._base_sensor import Sensor
from custom_types import sensor_types, config_types
from interfaces import communication_queue

I2C_BUS = 1
ADDRESS = 0x47
CHIP_ID = 0x51

REGISTER_CHIP_ID = 0x01
REGISTER_DATA = 0x1D  # temperature XLSB..MSB, then pressure XLSB..MSB
REGISTER_OSR_CONFIG = 0x36
REGISTER_ODR_CONFIG = 0x37

# pressure enabled, pressure oversampling 16x, temperature oversampling 2x
OSR_CONFIG = 0x40 | (0b100 << 3) | 0b001
# deep standby disabled
STANDBY_MODE = 0x80
FORCED_MODE = 0x80 | 0b10
MEASUREMENT_SECONDS = 0.1


def is_bmp585_connected() -> bool:
    """Probe the I2C bus for a BMP585 at its address."""
    try:
        with smbus2.SMBus(I2C_BUS) as bus:
            return bool(
                bus.read_byte_data(ADDRESS, REGISTER_CHIP_ID) == CHIP_ID)
    except OSError:
        return False


def decode_measurement(raw: list[int]) -> tuple[float, float]:
    """Convert the 6 data bytes to (°C, hPa)."""
    temperature_raw = raw[0] | raw[1] << 8 | raw[2] << 16
    if temperature_raw & 0x800000:
        temperature_raw -= 1 << 24
    pressure_raw = raw[3] | raw[4] << 8 | raw[5] << 16
    return temperature_raw / 2**16, pressure_raw / 2**6 / 100


class BoschBMP585(Sensor):
    """Class for the Bosch BMP585 sensor at the air inlet."""

    def __init__(self, config: config_types.Config,
                 communication_queue: communication_queue.CommunicationQueue):
        super().__init__(config=config,
                         communication_queue=communication_queue)

    def _initialize_sensor(self) -> None:
        """Initialize the sensor."""
        self.bus = smbus2.SMBus(I2C_BUS)
        chip_id = self.bus.read_byte_data(ADDRESS, REGISTER_CHIP_ID)
        if chip_id != CHIP_ID:
            raise self.SensorError(f"Unexpected BMP585 chip id {chip_id:#x}.")
        self.bus.write_byte_data(ADDRESS, REGISTER_ODR_CONFIG, STANDBY_MODE)
        self.bus.write_byte_data(ADDRESS, REGISTER_OSR_CONFIG, OSR_CONFIG)

    def _shutdown_sensor(self) -> None:
        """Shutdown the sensor."""
        self.bus.close()

    def _read(self, *args: Any,
              **kwargs: Any) -> sensor_types.BMP585SensorData:
        """Trigger one forced measurement and read it."""
        self.bus.write_byte_data(ADDRESS, REGISTER_ODR_CONFIG, FORCED_MODE)
        time.sleep(MEASUREMENT_SECONDS)
        raw = self.bus.read_i2c_block_data(ADDRESS, REGISTER_DATA, 6)
        temperature, pressure = decode_measurement(raw)
        return sensor_types.BMP585SensorData(
            temperature=round(temperature, 2),
            pressure=round(pressure, 2),
        )

    def _simulate_read(self, *args: Any,
                       **kwargs: Any) -> sensor_types.BMP585SensorData:
        """Simulate reading the sensor value."""
        return sensor_types.BMP585SensorData(
            temperature=round(random.uniform(0, 50), 2),
            pressure=round(random.uniform(900, 1050), 2),
        )
