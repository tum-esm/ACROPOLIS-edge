try:
    import smbus2
except ImportError:
    pass

from hardware.sensors.base_sensor import Sensor
from custom_types import config_types


class GroveMCP9808(Sensor):
    """Class for the Grove MCP9808 sensor."""

    def __init__(self, config: config_types.Config, simulate: bool = False):
        super().__init__(config=config, simulate=simulate)

    def _initialize_sensor(self) -> None:
        """Initialize the sensor."""
        self.bus = smbus2.SMBus(1)
        self.adress = 0x18
        self.register = 0x05

    def _shutdown_sensor(self) -> None:
        """Shutdown the sensor."""
        if self.bus:
            self.bus.close()

    def _read(self) -> float:
        """Read the sensor value."""

        result = self.bus.read_word_data(self.adress, self.register)

        # swap the bytes
        data = (result & 0xff) << 8 | (result & 0xff00) >> 8
        if data & 0x1000:
            data = -((data ^ 0x0FFF) + 1)
        else:
            data = data & 0x0fff
        return data / 16.0
