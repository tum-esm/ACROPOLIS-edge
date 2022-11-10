import queue
from typing import Literal
import serial
import time
import threading
from src import utils, types


# TODO: add pressure calibration
# TODO: add humidity calibration
# TODO: add oxygen calibration
# TODO: add temperature calibration
# TODO: verify received CO2 values with regex


class RS232Interface:
    receiving_queue: queue.Queue[str] = queue.Queue()

    def __init__(self) -> None:
        self.serial_interface = serial.Serial("/dev/ttySC0", 19200)
    
    def write(
        self,
        message: str,
        sleep: float | None = None,
        send_esc: bool = False,
        save_eeprom: bool = False,
    ) -> None:
        # TODO: add thread lock
        self.serial_interface.write(f"{'\x1B' if send_esc else ''}{message}\r\n".encode("utf-8"))
        if save_eeprom:
            self.rs232_interface.write("save\r\n".encode("utf-8"))
        self.serial_interface.flush()
        if sleep is not None:
            time.sleep(sleep)
    
    def read(self) -> str:
        # TODO: add thread lock
        waiting_bytes_count = self.serial_interface.inWaiting()
        if waiting_bytes_count > 0:
            received_bytes = self.serial_interface.read(waiting_bytes_count)
            if received_bytes[0] != 0:
                return received_bytes.decode("cp1252").replace(";", ",")
        return ""
    
    @staticmethod
    def data_receiving_loop():
        """Receiving all the data that is send over RS232 and print it.
        If the data is a CO2 measurement it will be safed in sensor log
        """
        accumulating_serial_stream = ""
        rs232_interface = RS232Interface()
        while True:
            accumulating_serial_stream += rs232_interface.read()
            splitted_serial_stream = accumulating_serial_stream.split("\n")
            for received_line in splitted_serial_stream[:-1]:
                RS232Interface.receiving_queue.put(received_line)
            accumulating_serial_stream = splitted_serial_stream[-1]
            
            time.sleep(0.001)

class CO2SensorInterface:
    thread_receiving_data = True
    last_oxygen = None
    last_pressure = None
    last_humidity = None

    def __init__(self, config: types.Config) -> None:
        self.rs232_interface = RS232Interface()
        self.logger = utils.Logger(config, origin="co2-sensor")

    def start_polling_measurements(self):
        self.rs232_interface.write("r", sleep=0.1)
        self.logger.info("started polling")
    
    def stop_polling_measurements(self):
        self.rs232_interface.write("s", sleep=0.1)
        self.logger.info("stopped polling")

    def start_receiving_data(self):
        """Start new thread for the receiving data over RS232
        it is a deamon thread that will be ended if the main thread is killed
        """
        threading.Thread(target=RS232Interface.data_receiving_loop, daemon=True).start()
        # TODO: log

    def set_filter_setting(
        self,
        median: int = 0,
        average: int = 10,
        smooth: int = 0,
        linear: bool = True,
        save_eeprom: bool = False,
    ):
        """Send the command for the filter settings
        Median first filters in chain, removing random peak values. Number of
        measurements is set by Median command (0 to 13 measurments)
        Averaging filter calculates moving average over period of time.
        Can be set from 0 to 60 seconds for longer averaging times use smoothing.
        0s => 3ppm; 10s => 2ppm; 30s => 1ppm
        Smoothing filter calculates the running average by weighting
            the most recent measurments.
        It is a factor that can be set between 0 to 255 and is calculated as follows:
            Smooting factor * 4 = approx. averaging time(s)
        The CO2 sensor is producing a signal which is not liear to the CO2 concentration
        The user can disable the internal linearization to achieve
            a signal proportioal to the absorption (True or False)
        """
        assert average >= 0 and average <= 60, "invalid calibration setting, average not in [0, 60]"
        assert smooth >= 0 and smooth <= 255, "invalid calibration setting, smooth not in [0, 255]"
        assert median >= 0 and median <= 13, "invalid calibration setting, median not in [0, 13]"

        self.rs232_interface.write(f"average {average}", send_esc=True)
        self.rs232_interface.write(f"smooth {smooth}", send_esc=True)
        self.rs232_interface.write(f"median {median}", send_esc=True)
        self.rs232_interface.write(
            f"linear {'on' if linear else 'off'}",
            send_esc=True,
            save_eeprom=save_eeprom,
            sleep=0.5
        )

        # TODO: log

    def set_measurement_interval(
        self,
        value: int = 1,
        unit: Literal["s", "min", "h"] = "s",
        save_eeprom: bool = False,
    ):
        """Send the command to set the time between the automatic measurment
        value can be selected between 1 to 1000."""

        assert 1 <= value <= 1000, "invalid interval setting"
        self.rs232_interface.write(f"intv {value} {unit}")
        if save_eeprom:
           self.rs232_interface.write("save")
        time.sleep(0.2)

        # TODO: log

    @staticmethod
    def set_time(clock_time: str, save_eeprom=False):
        """The function set the time of the CO2 Sensor.
        clock time is a string like "12:15:00"
        """
        clock_time_check = list(map(int, clock_time.split(":")))
        assert (
            clock_time_check[0] >= 0
            and clock_time_check[0] < 24
            and clock_time_check[1] >= 0
            and clock_time_check[1] < 60
            and clock_time_check[2] >= 0
            and clock_time_check[2] < 60
        ), "Wrong calibration setting"
        RS232.write(f"\x1B time {clock_time}\r\n".encode("utf-8"))

        if save_eeprom:
            RS232.write("save\r\n".encode("utf-8"))
        RS232.flush()
        time.sleep(0.1)

        logger.system_data_logger.info(f"Setting clock time {clock_time}")

    @staticmethod
    def get_time():
        """The function get the time of the CO2 Sensor since the last reset.
        return: String in the format of "12:10:04"
        """
        GMP343._receive_serial_cache(False)
        time.sleep(0.05)  # max runtime of one cycle in receiving data loop

        RS232.write("time\r\n".encode("utf-8"))
        RS232.flush()
        time.sleep(0.1)

        received_serial_cache = GMP343._receive_serial_cache(True)

        return received_serial_cache[6:14].decode("cp1252")

    def set_measurement_range(self, upper_limit: Literal[1000, 2000, 3000, 4000, 5000, 20000] = 1000, save_eeprom: bool = False):
        """Set the measurement range of the sensors"""
        self.rs232_interface.write(f"range {upper_limit}", send_esc=True, save_eeprom=save_eeprom, sleep=1)
        # TODO: log

    @staticmethod
    def set_formatting_message(
        raw_data=True,
        with_compensation_data=True,
        filtered_data=True,
        echo=True,
        save_eeprom=False,
    ):
        """Send the commands to format the measurement messages
        raw_data is the raw data before any compensations and filters (True or False)
        with_compensation_data is the data before the filters but with the
        enabled compensations like oxygen, humidity (True or False)
        filtered_data is the data after the compensations and enabled filters (True or False)
        echo defines if the sensor returns the sended commands (True or False)
        """
        formatting_string = "form "
        if raw_data:
            formatting_string += '"Raw"CO2RAWUC"ppm"'
            if with_compensation_data or filtered_data:
                formatting_string += '"; "'
        if with_compensation_data:
            formatting_string += '"Comp"CO2RAW"ppm"'
            if filtered_data:
                formatting_string += '"; "'
        if filtered_data:
            formatting_string += '"Filt"CO2"ppm"'
        formatting_string += "#r#n"

        RS232.write(f"\x1B {formatting_string}\r\n".encode("utf-8"))
        RS232.write(f"\x1B echo {'on' if echo else 'off'}\r\n".encode("utf-8"))

        if save_eeprom:
            RS232.write("save\r\n".encode("utf-8"))
        RS232.flush()
        time.sleep(1)

    @staticmethod
    def get_info(
        device_info=True, software_version=False, errors=False, corrections=False
    ):
        """Send diffrent information about the versions and settings of the CO2 sensor
        device_info shows name/software version, serien number, last calibration,
            measurment span, pressure, humidity, oxygen, compensations, interface
        software_version shows software version (also in device_info)
        errors shows the error messages that are received
        corrections shows the last linear and multipoint correction value
        return: string of the complete answer of the CO2 sensor
        """
        GMP343._receive_serial_cache(False)

        if device_info:
            RS232.write("??\r\n".encode("utf-8"))
        if software_version:
            RS232.write("vers\r\n".encode("utf-8"))
        if errors:
            RS232.write("errs\r\n".encode("utf-8"))
        if corrections:
            RS232.write("corr\r\n".encode("utf-8"))

        RS232.flush()
        time.sleep(1)

        received_serial_cache = GMP343._receive_serial_cache(True)

        return received_serial_cache.decode("cp1252")

    def _receive_serial_cache(thread_receiving_data: bool):
        """Internal class function that can stop or start the receiving data
        in the deamon thread. Also empty the serial cache and returns the bytearray
        """
        if not thread_receiving_data:
            GMP343.thread_receiving_data = thread_receiving_data
            time.sleep(0.05)  # max runtime of one cycle in receiving data loop

        received_serial_cache = bytearray(0)
        while RS232.inWaiting() > 0:
            received_serial_cache = RS232.read(RS232.inWaiting())

        if thread_receiving_data:
            # stop/start the deamon thread until the return value
            GMP343.thread_receiving_data = thread_receiving_data
            time.sleep(0.05)  # max runtime of one cycle in receiving data loop

        return received_serial_cache
