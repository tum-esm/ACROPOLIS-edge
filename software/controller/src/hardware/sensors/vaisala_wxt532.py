import random
import time
import re
from typing import Any, Optional, Tuple, List, Match

try:
    import gpiozero
    import gpiozero.pins.pigpio
    import serial
except Exception:
    pass

from hardware.sensors._base_sensor import Sensor
from custom_types import config_types, sensor_types
from utils import list_operations
from interfaces import communication_queue

# Regex patterns for parsing wind sensor messages
MEASUREMENT_PATTERN = (
    r"Dn=([0-9.]+)D,Dm=([0-9.]+)D,Dx=([0-9.]+)D,Sn=([0-9.]+)M,Sm=([0-9.]+)M,Sx=([0-9.]+)M"
)
DEVICE_STATUS_PATTERN = (
    r"Th=([0-9.]+)C,Vh=([0-9.]+)N,Vs=([0-9.]+)V,Vr=([0-9.]+)V")


class SerialInterface:

    def __init__(self, port: str, encoding: str = "cp1252") -> None:
        self.serial_interface = serial.Serial(
            port=port,
            baudrate=19200,
            bytesize=8,
            parity="N",
            stopbits=1,
        )
        self.encoding = encoding

    def flush_receiver_stream(self) -> None:
        """Wait briefly and flush the input buffer."""
        time.sleep(0.2)
        self.serial_interface.reset_input_buffer()

    def read_all(self) -> Any:
        """Read all available data from the serial port and decode it."""
        raw_bytes = self.serial_interface.read_all()
        return raw_bytes.decode(self.encoding) if raw_bytes else ""


class VaisalaWXT532(Sensor):
    """Class for the Vaisala WXT532 wind sensor."""

    def __init__(self, config: config_types.Config,
                 communication_queue: communication_queue.CommunicationQueue,
                 pin_factory: gpiozero.pins.pigpio.PiGPIOFactory) -> None:
        super().__init__(config=config,
                         communication_queue=communication_queue,
                         pin_factory=pin_factory)
        self.buffered_messages: List[str] = []
        self.latest_device_status: Optional[
            sensor_types.WindSensorStatus] = None

    def _initialize_sensor(self) -> None:
        """Initialize the wind sensor."""
        self.power_pin = gpiozero.OutputDevice(
            pin=self.config.hardware.wxt532_power_pin_out,
            pin_factory=self.pin_factory)
        self.power_pin.on()
        self.serial_interface = SerialInterface(
            port=str(self.config.hardware.wxt532_serial_port))
        self.current_input_stream = ""

    def _shutdown_sensor(self) -> None:
        """Shutdown the sensor and release resources."""
        if hasattr(
                self,
                "power_pin") and self.power_pin and not self.power_pin.closed:
            self.power_pin.off()
            self.power_pin.close()
        else:
            self.logger.warning(
                "Power pin is uninitialized or already closed.")

    def _read(
        self, *args: Any, **kwargs: Any
    ) -> Tuple[Optional[sensor_types.WindSensorData],
               Optional[sensor_types.WindSensorStatus]]:
        """Read the wind sensor data and device status."""
        self._update_buffered_messages()
        wind_measurements = self._extract_measurements_from_messages()
        aggregated_measurement = self._aggregate_measurements(
            wind_measurements)
        return aggregated_measurement, self.latest_device_status

    def _simulate_read(
        self
    ) -> Tuple[Optional[sensor_types.WindSensorData],
               Optional[sensor_types.WindSensorStatus]]:
        """Simulate the wind sensor data and device status."""
        now = round(time.time())
        return (sensor_types.WindSensorData(
            speed_avg=round(random.uniform(0, 20), 2),
            speed_max=round(random.uniform(0, 20), 2),
            speed_min=round(random.uniform(0, 20), 2),
            direction_avg=round(random.uniform(0, 360), 2),
            direction_max=round(random.uniform(0, 360), 2),
            direction_min=round(random.uniform(0, 360), 2),
            last_update_time=now,
        ),
                sensor_types.WindSensorStatus(
                    temperature=round(random.uniform(-20, 60), 2),
                    heating_voltage=round(random.uniform(0, 24), 2),
                    supply_voltage=round(random.uniform(0, 24), 2),
                    reference_voltage=round(random.uniform(0, 5), 2),
                    last_update_time=now,
                ))

    def _update_buffered_messages(self) -> None:
        """
        Update the internal buffer by reading new data from the serial interface,
        splitting into complete messages.
        """
        new_data = self.serial_interface.read_all()
        if not new_data:
            return
        self.current_input_stream += new_data
        messages = self.current_input_stream.split("\r\n")
        self.current_input_stream = messages[
            -1]  # Retain any incomplete message
        self.buffered_messages.extend(messages[:-1])

    def _extract_measurements_from_messages(
            self) -> List[sensor_types.WindSensorData]:
        """
        Extract wind sensor measurements and update device status from buffered messages.
        """
        wind_measurements: List[sensor_types.WindSensorData] = []
        for message in self.buffered_messages:
            measurement_match = re.search(MEASUREMENT_PATTERN, message)
            if measurement_match:
                wind_measurements.append(
                    self._parse_measurement_message(measurement_match))
            device_match = re.search(DEVICE_STATUS_PATTERN, message)
            if device_match:
                self.latest_device_status = self._parse_device_status_message(
                    device_match)
        self.buffered_messages.clear()
        return wind_measurements

    def _parse_measurement_message(
            self, match: Match[str]) -> sensor_types.WindSensorData:
        """Parse a measurement message into a WindSensorData object."""
        return sensor_types.WindSensorData(
            direction_min=float(match.group(1)),
            direction_avg=float(match.group(2)),
            direction_max=float(match.group(3)),
            speed_min=float(match.group(4)),
            speed_avg=float(match.group(5)),
            speed_max=float(match.group(6)),
            last_update_time=round(time.time()),
        )

    def _parse_device_status_message(
            self, match: Match[str]) -> sensor_types.WindSensorStatus:
        """Parse a device status message into a WindSensorStatus object."""
        return sensor_types.WindSensorStatus(
            temperature=float(match.group(1)),
            heating_voltage=float(match.group(2)),
            supply_voltage=float(match.group(3)),
            reference_voltage=float(match.group(4)),
            last_update_time=round(time.time()),
        )

    def _aggregate_measurements(
        self, wind_measurements: List[sensor_types.WindSensorData]
    ) -> Optional[sensor_types.WindSensorData]:
        """
        Aggregate multiple wind measurements into a single summary value.
        """
        if not wind_measurements:
            return None
        self.logger.info(
            f"Processed {len(wind_measurements)} wind sensor measurements.")
        return sensor_types.WindSensorData(
            direction_min=min(m.direction_min for m in wind_measurements),
            direction_avg=list_operations.circular_mean_degrees(
                [m.direction_avg for m in wind_measurements], 1),
            direction_max=max(m.direction_max for m in wind_measurements),
            speed_min=min(m.speed_min for m in wind_measurements),
            speed_avg=list_operations.avg_list(
                [m.speed_avg for m in wind_measurements], 1),
            speed_max=max(m.speed_max for m in wind_measurements),
            last_update_time=max(m.last_update_time
                                 for m in wind_measurements),
        )
        #TODO: Implement Max/Min function that works for wind direction to avoid issues with wrap-around at 0/360 degrees.

    def _check_errors(self) -> None:
        """
        Check the device status for errors.
        """
        if not self.latest_device_status:
            self.logger.info("No device status available.")
            return
        now = time.time()
        if now - self.latest_device_status.last_update_time > 300:
            self.logger.warning("Device status is older than 5 minutes.")
            return
        assert 22 <= self.latest_device_status.heating_voltage <= 26, "Heating voltage out of range"
        assert 22 <= self.latest_device_status.supply_voltage <= 26, "Supply voltage out of range"
        assert 3.2 <= self.latest_device_status.reference_voltage <= 4.0, "Reference voltage out of range"
