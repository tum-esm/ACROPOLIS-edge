import random
import time
from typing import Any, Optional, Literal
import re

try:
    import gpiozero
    import gpiozero.pins.pigpio
    import serial
except Exception:
    pass

from hardware.sensors._base_sensor import Sensor
from custom_types import sensor_types, config_types
from interfaces import communication_queue

# Regex patterns for CO₂ sensor responses
CO2_MEASUREMENT_REGEX = (
    r"\d+\.\d+\s+"  # raw
    + r"\d+\.\d+\s+"  # compensated
    + r"\d+\.\d+\s+"  # compensated + filtered
    + r"\d+\.\d+\s+"  # temperature
    + r"\(R C C\+F T\)")
STARTUP_REGEX = r"GMP343 - Version STD \d+\.\d+\\r\\n" + \
                r"Copyright: Vaisala Oyj \d{4} - \d{4}"


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

    def send_command(
        self,
        message: str,
        expected_regex: str = r".*\>.*",
        timeout: float = 8
    ) -> tuple[Literal["success", "uncomplete", "timeout"], str]:
        """
        Send a command to the sensor and wait for a response that matches the expected regex.
        """
        self.flush_receiver_stream()
        self.serial_interface.write(f"{message}\r\n".encode("utf-8"))
        self.serial_interface.flush()
        return self.wait_for_answer(expected_regex=expected_regex,
                                    timeout=timeout)

    def wait_for_answer(
        self, expected_regex: str, timeout: float
    ) -> tuple[Literal["success", "uncomplete", "timeout"], str]:
        start_time = time.time()
        answer = ""
        while True:
            answer_chunk = self.read_all()
            if answer_chunk:
                answer += answer_chunk
                if re.search(expected_regex, answer):
                    return "success", answer
                if re.search(r".*\?.*", answer):
                    return "uncomplete", answer
            if (time.time() - start_time) > timeout:
                return "timeout", answer
            time.sleep(0.05)


class VaisalaGMP343(Sensor):
    """Class for the Vaisala GMP343 sensor."""

    def __init__(self, config: config_types.Config,
                 communication_queue: communication_queue.CommunicationQueue,
                 pin_factory: gpiozero.pins.pigpio.PiGPIOFactory):
        super().__init__(config=config,
                         communication_queue=communication_queue,
                         pin_factory=pin_factory)

    def _initialize_sensor(self) -> None:
        """Initialize the sensor."""
        self.power_pin = gpiozero.OutputDevice(
            pin=self.config.hardware.gmp343_power_pin_out,
            pin_factory=self.pin_factory)
        self.last_powerup_time = time.time()
        self.power_pin.off()
        time.sleep(5)
        self.power_pin.on()
        self.serial_interface = SerialInterface(
            port=str(self.config.hardware.gmp343_serial_port))
        self.serial_interface.flush_receiver_stream()
        self.serial_interface.wait_for_answer(expected_regex=STARTUP_REGEX,
                                              timeout=10)
        self._send_sensor_settings()
        

    def _shutdown_sensor(self) -> None:
        """Shutdown the sensor."""
        if hasattr(
                self,
                "power_pin") and self.power_pin and not self.power_pin.closed:
            self.power_pin.off()
            # Shut down the device and release all associated resources (such as GPIO pins).
            self.power_pin.close()
        else:
            self.logger.warning(
                "Power pin is uninitialized or already closed.")

    def _read(self, *args: Any,
              **kwargs: Optional[float]) -> sensor_types.CO2SensorData:
        """Read the sensor value."""
        humidity = kwargs.get('humidity', None)
        pressure = kwargs.get('pressure', None)

        # set compensation values if provided
        if (humidity is not None) and (pressure is not None):
            self._send_compensation_values(pressure=pressure,
                                           humidity=humidity)
        answer = self.serial_interface.send_command(
            "send", expected_regex=CO2_MEASUREMENT_REGEX, timeout=15)
        if not answer[1] or 'Unknown' in answer[1]:
            raise self.SensorError(
                "Invalid sensor response: data missing or corrupted.")
        try:
            sensor_data = tuple(map(float, answer[1].split()[:4]))
        except ValueError as e:
            self.logger.error(f"Failed to parse sensor data: {e}")
            raise self.SensorError("Failed to parse sensor data.")
        return sensor_types.CO2SensorData(
            raw=sensor_data[0],
            compensated=sensor_data[1],
            filtered=sensor_data[2],
            temperature=sensor_data[3],
        )

    def _simulate_read(self, *args: Any,
                       **kwargs: Any) -> sensor_types.CO2SensorData:
        """Simulate the sensor value."""
        return sensor_types.CO2SensorData(
            raw=random.uniform(0, 1000),
            compensated=random.uniform(0, 1000),
            filtered=random.uniform(0, 1000),
            temperature=random.uniform(0, 50),
        )

    def _retry_send_command(self, command: str, error_type: str,
                            expected_regex: str, timeout: float) -> str:
        """
        Extracted retry logic for sending commands.
        """
        answer = self.serial_interface.send_command(
            message=command.strip().split(" ")[-1]
            if error_type == "uncomplete" else command,
            expected_regex=expected_regex,
            timeout=timeout)
        if answer[0] == "success":
            self.logger.info(f"Resending {error_type} was successful.")
            return self._format_raw_answer(answer[1])
        raise self.SensorError(
            f"Resend failed: {error_type}. Sensor answer: {answer[1]}")

    def _send_command_to_sensor(self,
                                command: str,
                                expected_regex: str = r".*\>.*",
                                timeout: float = 8) -> str:
        """
        Send a command and handle responses, using the extracted retry logic.
        """
        answer = self.serial_interface.send_command(
            message=command, expected_regex=expected_regex, timeout=timeout)
        if answer[0] == "success":
            return self._format_raw_answer(answer[1])
        if answer[0] in ("uncomplete", "timeout"):
            return self._retry_send_command(command, answer[0], expected_regex,
                                            timeout)
        raise self.SensorError("Sending command failed")

    def _send_sensor_settings(self) -> None:
        """Send sensor settings defined in the configuration file."""
        self.logger.info("Sending settings to the CO₂ sensor.")
        settings = [
            'form CO2RAWUC CO2RAW CO2 T " (R C C+F T)"',
            'echo off',
            'range 1',
            f"average {self.config.hardware.gmp343_filter_seconds_averaging}",
            f"smooth {self.config.hardware.gmp343_filter_smoothing_factor}",
            f"median {self.config.hardware.gmp343_filter_median_measurements}",
            f"heat {'on' if self.config.hardware.gmp343_optics_heating else 'off'}",
            f"linear {'on' if self.config.hardware.gmp343_linearisation else 'off'}",
            f"tc {'on' if self.config.hardware.gmp343_temperature_compensation else 'off'}",
            f"rhc {'on' if self.config.hardware.gmp343_relative_humidity_compensation else 'off'}",
            f"pc {'on' if self.config.hardware.gmp343_pressure_compensation else 'off'}",
            f"oc {'on' if self.config.hardware.gmp343_oxygen_compensation else 'off'}",
        ]
        for command in settings:
            self._send_command_to_sensor(command=command)
        self.logger.info("Settings sent successfully.")

    def _send_compensation_values(self, pressure: float,
                                  humidity: float) -> None:
        """Update sensor with pressure and humidity compensation values."""
        if not (0 <= humidity <= 100):
            raise ValueError(f"Humidity {humidity} is out of range [0, 100].")
        if not (700 <= pressure <= 1300):
            raise ValueError(
                f"Pressure {pressure} is out of range [700, 1300].")
        self._send_command_to_sensor(command=f"rh {round(humidity, 2)}")
        self._send_command_to_sensor(command=f"p {round(pressure, 2)}")
        self.logger.info(
            f"Updated compensation values: pressure = {pressure}, humidity = {humidity}."
        )

    def _format_raw_answer(self, raw: str) -> str:
        """Format and clean up the raw sensor answer."""
        return (raw.strip(" \r\n").replace(
            "  ", "").replace(" : ", ": ").replace(" \r\n", "\r\n").replace(
                "\r\n\r\n", "\r\n").replace("\r\n", "; ").removesuffix("; >"))

    def _check_errors(self) -> None:
        """
        Check sensor for errors.
        """
        answer = self._send_command_to_sensor("param")
        self.logger.info(f"GMP343 Sensor Info: {answer}")
        answer = self._send_command_to_sensor("errs")
        if "OK: No errors detected." not in answer:
            self.logger.warning(f"The CO₂ sensor reported errors: {answer}",
                                forward=True)
            raise self.SensorError("CO₂ sensor reported errors.")
