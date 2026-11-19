import glob
import os
import re
import time
from typing import Any, Optional

try:
    import serial
except Exception:
    pass

from hardware.sensors._base_sensor import Sensor
from custom_types import config_types, sensor_types
from interfaces import communication_queue

SIMCOM_USB_VENDOR_ID = "1e0e"
# interface 02 is the AT command port, the port number (ttyUSBx) differs between systems
SIMCOM_AT_INTERFACE = "02"
USB_SERIAL_SYSFS_PATH = "/sys/bus/usb-serial/devices"
AT_COMMAND_TIMEOUT_SECONDS = 2
# Kite SIMs carry no data over Telekom (national roaming), so the modem must not leave O2.
# 262-03 is what acropolis-4 reports on O2 (+CPSI)
O2_GERMANY_PLMN = "26203"
NETWORK_REGISTRATION_TIMEOUT_SECONDS = 120
NETWORK_LOCK_RETRY_SECONDS = 3600


def find_at_port(sysfs_path: str = USB_SERIAL_SYSFS_PATH) -> Optional[str]:
    """Returns the AT command port of the SIMCom modem, None if there is no modem.
    Uses sysfs because /dev/serial/by-id does not exist inside the container."""

    for tty_path in sorted(glob.glob(os.path.join(sysfs_path, "ttyUSB*"))):
        interface_path = os.path.realpath(os.path.join(tty_path, ".."))
        try:
            with open(os.path.join(interface_path, "bInterfaceNumber")) as f:
                interface = f.read().strip()
            with open(os.path.join(interface_path, "..", "idVendor")) as f:
                vendor = f.read().strip()
        except OSError:
            continue
        if vendor == SIMCOM_USB_VENDOR_ID and interface == SIMCOM_AT_INTERFACE:
            return "/dev/" + os.path.basename(tty_path)
    return None


def parse_csq(response: str) -> Optional[float]:
    """+CSQ: <rssi>,<ber> with rssi 0..31 = -113..-51 dBm, 99 = unknown"""

    match = re.search(r"\+CSQ: (\d+),", response)
    if match is None or not 0 <= int(match.group(1)) <= 31:
        return None
    return -113 + 2 * int(match.group(1))


def parse_cpsi(response: str) -> dict[str, Any]:
    """+CPSI: LTE,Online,262-03,0xC945,25885738,204,EUTRAN-BAND3,1600,5,5,-123,-951,-611,14
    LTE fields 10 to 13: RSRQ and RSRP and RSSI in 1/10 dB(m), SINR in dB."""

    match = re.search(r"\+CPSI: (.*)", response)
    if match is None:
        return {}
    fields = [field.strip() for field in match.group(1).split(",")]
    result: dict[str, Any] = {"rat": fields[0]}
    if fields[0] == "LTE" and len(fields) >= 14:
        result.update(
            band=fields[6],
            rsrq_db=int(fields[10]) / 10,
            rsrp_dbm=int(fields[11]) / 10,
            sinr_db=float(fields[13]),
        )
    return result


def parse_iccid(response: str) -> Optional[str]:
    match = re.search(r"\+ICCID: (\w+)", response)
    return match.group(1) if match else None


def parse_imei(response: str) -> Optional[str]:
    match = re.search(r"\b(\d{15})\b", response)
    return match.group(1) if match else None


def parse_operator(response: str) -> Optional[str]:
    match = re.search(r'\+COPS: \d+,\d+,"([^"]*)"', response)
    return match.group(1) if match else None


def is_automatic_network_selection(response: str) -> bool:
    return re.search(r"\+COPS: 0\b", response) is not None


class SimcomSIM7600(Sensor):
    """Class for the SIMCom SIM7600 LTE modem, AT queries and the O2 network lock.

    The modem is optional: without it, all values are None. The data connection
    runs over QMI (simcom-cm), so the AT port is free."""

    def __init__(self, config: config_types.Config,
                 communication_queue: communication_queue.CommunicationQueue):
        super().__init__(config=config,
                         communication_queue=communication_queue)
        self.last_network_lock_time: Optional[float] = None

    def _initialize_sensor(self) -> None:
        """The port is opened per read, so a missing modem cannot stop the controller."""
        pass

    def _shutdown_sensor(self) -> None:
        pass

    def _read(self, *args: Any, **kwargs: Any) -> sensor_types.ModemData:
        port = find_at_port()
        if port is None:
            self.logger.debug("No SIMCom modem found.")
            return sensor_types.ModemData()

        with serial.Serial(port=port,
                           baudrate=115200,
                           timeout=AT_COMMAND_TIMEOUT_SECONDS) as interface:
            cops = self._send_command(interface, "AT+COPS?")
            if is_automatic_network_selection(cops):
                self._lock_network_to_o2(interface)
            cpsi = parse_cpsi(self._send_command(interface, "AT+CPSI?"))
            data = sensor_types.ModemData(
                rssi_dbm=parse_csq(self._send_command(interface, "AT+CSQ")),
                rsrp_dbm=cpsi.get("rsrp_dbm"),
                rsrq_db=cpsi.get("rsrq_db"),
                sinr_db=cpsi.get("sinr_db"),
                rat=cpsi.get("rat"),
                band=cpsi.get("band"),
                operator=parse_operator(cops),
                iccid=parse_iccid(self._send_command(interface,
                                                     "AT+CICCID")),
                imei=parse_imei(self._send_command(interface, "AT+CGSN")),
            )
        self.logger.debug(f"Modem: {data}")
        return data

    def _lock_network_to_o2(self, interface: Any) -> None:
        if (self.last_network_lock_time is not None and time.time() -
                self.last_network_lock_time < NETWORK_LOCK_RETRY_SECONDS):
            return
        self.last_network_lock_time = time.time()
        response = self._send_command(
            interface, f'AT+COPS=1,2,"{O2_GERMANY_PLMN}",7',
            NETWORK_REGISTRATION_TIMEOUT_SECONDS)
        # the lock switches +COPS? to numeric, keep reporting the operator name
        self._send_command(interface, "AT+COPS=3,0")
        if "OK" in response:
            self.logger.info(f"Locked modem to O2 ({O2_GERMANY_PLMN}).")
        else:
            self.logger.warning(
                f"Could not lock modem to O2 ({O2_GERMANY_PLMN}): {response.strip()}")

    def _send_command(self,
                      interface: Any,
                      command: str,
                      timeout_seconds: float = AT_COMMAND_TIMEOUT_SECONDS) -> str:
        """Returns the response up to OK or ERROR, raises on timeout."""
        interface.reset_input_buffer()
        interface.write(f"{command}\r".encode())
        response = b""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response += interface.read(interface.in_waiting or 1)
            if b"OK\r\n" in response or b"ERROR" in response:
                return response.decode(errors="replace")
        raise TimeoutError(f"No response to {command}: {response!r}")

    def _simulate_read(self, *args: Any,
                       **kwargs: Any) -> sensor_types.ModemData:
        return sensor_types.ModemData(rssi_dbm=-63,
                                      rsrp_dbm=-95.1,
                                      rsrq_db=-12.3,
                                      sinr_db=14,
                                      rat="LTE",
                                      band="EUTRAN-BAND3",
                                      operator="o2 - de",
                                      iccid="8934076100000000000",
                                      imei="860000000000000")
