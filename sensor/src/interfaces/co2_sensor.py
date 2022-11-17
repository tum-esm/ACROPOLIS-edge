import queue
import serial
import time
import threading
from src import utils, types


# returned when calling "send"
measurement_regex = r"Raw\s*\d+\.\dppm;\sComp\s*\d+\.\dppm;\sFilt\s*\d+\.\dppm"

# returned when calling "errs"
error_regex = r"OK: No errors detected\."

# returned when calling "average x"/"smooth x"/"median x"/"linear x"
filter_settings_regex = r"(AVERAGE \(s\)|SMOOTH|MEDIAN|LINEAR)\s*:\s(\d{1,3}|ON|OFF)"

# returned when calling "??"
sensor_info_regex = r"\n".join(
    [
        r"GMP343 / \d+\.\d+",
        r"SNUM           : .*",
        r"CALIBRATION    : \d{4}\-\d{4}\-\d{4}",
        r"CAL\. INFO      : .*",
        r"SPAN \(ppm\)     : 1000",
        r"PRESSURE \(hPa\) : \d+\.\d+",
        r"HUMIDITY \(%RH\) : \d+\.\d+",
        r"OXYGEN \(%\)     : \d+\.\d+",
        r"PC             : (ON|OFF)",
        r"RHC            : (ON|OFF)",
        r"TC             : (ON|OFF)",
        r"OC             : (ON|OFF)",
        r"ADDR           : .*",
        r"ECHO           : OFF",
        r"SERI           : 19200 8 NONE 1",
        r"SMODE          : .*",
        r"INTV           : .*",
    ]
)

# TODO: add pressure calibration
# TODO: add humidity calibration
# TODO: add oxygen calibration
# TODO: add temperature calibration
# TODO: verify received CO2 values with regex

rs232_lock = threading.Lock()
rs232_receiving_queue: queue.Queue[str] = queue.Queue()


class _RS232Interface:
    def __init__(self) -> None:
        self.serial_interface = serial.Serial("/dev/ttySC0", 19200)

    def write(
        self,
        message: str,
        sleep: float | None = None,
        send_esc: bool = False,
        save_eeprom: bool = False,
    ) -> None:
        with rs232_lock:
            self.serial_interface.write(
                (("\x1B " if send_esc else "") + message + "\r\n").encode("utf-8")
            )
            if save_eeprom:
                self.serial_interface.write("save\r\n".encode("utf-8"))
            self.serial_interface.flush()

        if sleep is not None:
            time.sleep(sleep)

    def read(self) -> str:
        received_bytes: bytes = self.serial_interface.read(self.serial_interface.in_waiting)
        return received_bytes.decode(encoding="cp1252").replace(";", ",")

    @staticmethod
    def data_receiving_loop(queue: queue.Queue[str]) -> None:
        """Receiving all the data that is send over RS232 and print it.
        If the data is a CO2 measurement it will be safed in sensor log
        """
        accumulating_serial_stream = ""
        rs232_interface = _RS232Interface()
        while True:
            accumulating_serial_stream += rs232_interface.read()

            splitted_serial_stream = accumulating_serial_stream.split("\n")
            for received_line in splitted_serial_stream[:-1]:
                queue.put(received_line)
            accumulating_serial_stream = splitted_serial_stream[-1]

            time.sleep(0.5)


class CO2SensorInterface:
    def __init__(self, config: types.Config) -> None:
        self.rs232_interface = _RS232Interface()
        self.logger = utils.Logger(config, origin="co2-sensor")

        time.sleep(3)

        for default_setting in [
            "echo off",
            "range 1000",
            'form "Raw"CO2RAWUC"ppm"; "Comp"CO2RAW"ppm"; "Filt"CO2"ppm"#r#n',
        ]:
            self.rs232_interface.write(default_setting, send_esc=True, save_eeprom=True, sleep=1)

        threading.Thread(
            target=_RS232Interface.data_receiving_loop, args=(rs232_receiving_queue,), daemon=True
        ).start()
        self.logger.info("started RS232 receiver thread")

    def get_latest_measurements(self) -> list[str]:
        measurements: list[str] = []
        while True:
            try:
                measurements.append(rs232_receiving_queue.get_nowait())
            except queue.Empty:
                break
        return measurements

    def set_filter_setting(
        self,
        median: int = 0,
        average: int = 10,
        smooth: int = 0,
        linear: bool = True,
    ) -> None:
        # TODO: construct a few opinionated measurement setups

        assert average >= 0 and average <= 60, "invalid calibration setting, average not in [0, 60]"
        assert smooth >= 0 and smooth <= 255, "invalid calibration setting, smooth not in [0, 255]"
        assert median >= 0 and median <= 13, "invalid calibration setting, median not in [0, 13]"

        self.rs232_interface.write(f"average {average}", send_esc=True)
        self.rs232_interface.write(f"smooth {smooth}", send_esc=True)
        self.rs232_interface.write(f"median {median}", send_esc=True)
        self.rs232_interface.write(f"linear {'on' if linear else 'off'}", send_esc=True, sleep=0.5)
        self.logger.info(
            f"set filter settings: average = {average}, smooth = {smooth}, "
            + f"median = {median}, linear = {linear}"
        )

    def get_sensor_info(self):
        self.rs232_interface.write("??")
        self.logger.debug("requested info: device info")

    def get_sensor_errors(self):
        self.rs232_interface.write("errs")
        self.logger.debug("requested info: errors")
