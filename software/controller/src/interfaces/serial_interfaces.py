import fcntl
import re
import time
from typing import Literal
import serial


class SerialCO2SensorInterface:

    def __init__(self, port: str) -> None:
        self.serial_interface = serial.Serial(
            port=port,
            baudrate=19200,
            bytesize=8,
            parity="N",
            stopbits=1,
        )

    def send_command(
        self,
        message: str,
        expected_regex: str = r".*\>.*",
        timeout: float = 8
    ) -> tuple[Literal["success", "uncomplete", "timeout"], str]:
        """
        send a command to the sensor. Puts a "\x1B" string after the
        command, which will make the sensor wait until commands
        have been processed.
        Returns the sensor answer as tuple (indicator, answer).
        """
        self.flush_receiver_stream()  # empty input queue
        self.serial_interface.write(
            f"{message}\r\n".encode("utf-8"))  # send command
        self.serial_interface.flush()  # wait until data is written
        return self.wait_for_answer(expected_regex=expected_regex,
                                    timeout=timeout)  # return answer

    def flush_receiver_stream(self) -> None:
        """wait 0.2 seconds and then empty the current input queue"""
        time.sleep(0.2)  # wait for outstanding answers from previous commands
        self.serial_interface.read_all(
        )  # reads everything in queue and throws it away

    def wait_for_answer(
        self, expected_regex: str, timeout: float
    ) -> tuple[Literal["success", "uncomplete", "timeout"], str]:
        start_time = time.time()
        answer = ""

        while True:
            received_bytes = self.serial_interface.read_all()
            if received_bytes is not None:
                answer += received_bytes.decode(encoding="cp1252")

                # return successful answer as it matches expected regex
                if re.search(expected_regex, answer):
                    return "success", answer

                # return answer that is requesting to set the new value in another message
                # this can happen if only "p" is received instead of "p 1000"
                # Example answer: "PRESSURE (hPa) : 1000.000 ?"
                if re.search(r".*\?.*", answer):
                    return "uncomplete", answer

            if (time.time() - start_time) > timeout:
                return "timeout", answer
            else:
                time.sleep(0.05)
