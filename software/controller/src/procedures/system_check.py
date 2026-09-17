import time
from typing import Optional, Any
try:
    import psutil
except Exception:
    pass

from custom_types import config_types, sensor_types
from custom_types import mqtt_playload_types
from interfaces import hardware_interface, logging_interface, communication_queue
from utils import system_info

MODEM_INFO_INTERVAL_SECONDS = 3600


class DiskUsageError(Exception):
    """Custom exception for disk usage errors."""
    pass

class SystemCheckProcedure:
    """runs every mainloop call"""

    def __init__(
            self, config: config_types.Config,
            communication_queue: communication_queue.CommunicationQueue,
            hardware_interface: hardware_interface.HardwareInterface) -> None:

        self.logger, self.config = logging_interface.Logger(
            config=config,
            communication_queue=communication_queue,
            origin="system-check-procedure"), config
        self.hardware_interface = hardware_interface
        self.communication_queue = communication_queue
        self.simulate = config.active_components.simulation_mode
        self.last_modem_info_time: Optional[float] = None

    def run(self) -> None:
        """runs system check procedure

        - log mainboard/CPU temperature
        - log enclosure humidity and pressure
        - check whether mainboard/CPU temperature is above 70°C
        - log CPU/disk/memory usage
        - check whether CPU/disk/memory usage is above 80%
        - check hardware interfaces for errors
        - log modem signal, and modem/SIM info hourly
        """

        cpu_temperature = self.cpu_temperature()
        cpu_usage = self.cpu_usage()
        disk_usage = self.disk_usage()
        memory_usage = self.memory_usage()
        ups_sate = self.hardware_interface.ups.read()
        mainboard_sensor = self.mainboard_sensor()
        modem = self.modem()

        # construct message and put it into message queue
        self.communication_queue.enqueue_message(
            type="measurement",
            payload=mqtt_playload_types.MQTTSystemData(
                enclosure_bme280_temperature=mainboard_sensor.temperature,
                enclosure_bme280_humidity=mainboard_sensor.humidity,
                enclosure_bme280_pressure=mainboard_sensor.pressure,
                raspi_cpu_temperature=cpu_temperature,
                raspi_disk_usage=disk_usage,
                raspi_cpu_usage=cpu_usage,
                raspi_memory_usage=memory_usage,
                ups_powered_by_grid=ups_sate.ups_powered_by_grid,
                ups_battery_is_fully_charged=ups_sate.
                ups_battery_is_fully_charged,
                ups_battery_error_detected=ups_sate.ups_battery_error_detected,
                ups_battery_above_voltage_threshold=ups_sate.
                ups_battery_above_voltage_threshold,
                modem_rssi_dbm=modem.rssi_dbm,
                modem_rsrp_dbm=modem.rsrp_dbm,
                modem_rsrq_db=modem.rsrq_db,
                modem_sinr_db=modem.sinr_db),
        )

        if modem.iccid is not None and (
                self.last_modem_info_time is None or time.time() -
                self.last_modem_info_time > MODEM_INFO_INTERVAL_SECONDS):
            self.communication_queue.enqueue_message(
                type="measurement",
                payload=mqtt_playload_types.MQTTModemInfo(
                    modem_rat=modem.rat,
                    modem_band=modem.band,
                    modem_operator=modem.operator,
                    modem_iccid=modem.iccid,
                    modem_imei=modem.imei),
            )
            self.last_modem_info_time = time.time()

        # check for hardware errors
        self.hardware_interface.check_errors()

    def cpu_temperature(self) -> Optional[float]:
        cpu_temperature = system_info.get_cpu_temperature(self.simulate)
        self.logger.debug(f"raspi cpu temp. = {cpu_temperature} °C")

        if (cpu_temperature is not None) and (cpu_temperature > 70):
            self.logger.warning(
                f"CPU temperature is very high ({cpu_temperature} °C)",
                forward=True,
            )

        return cpu_temperature

    def disk_usage(self) -> float:
        # evaluate disk usage
        disk_usage = psutil.disk_usage("/")
        self.logger.debug(
            f"{round(disk_usage.used/1_000_000)}/{round(disk_usage.total/1_000_000)} "
            + f"MB disk space used (= {disk_usage.percent} %)")
        if disk_usage.percent > 80:
            self.logger.warning(
                f"disk space usage is very high ({disk_usage.percent} %)",
                forward=True,
            )

        return round(disk_usage.percent / 100, 4)

    def cpu_usage(self) -> float:
        "Read RPi CPU usage"

        cpu_usage_percent = psutil.cpu_percent()
        self.logger.debug(f"{cpu_usage_percent} % total CPU usage")
        if cpu_usage_percent > 80:
            self.logger.warning(
                f"CPU usage is very high ({cpu_usage_percent} %)",
                forward=True)
            raise DiskUsageError("Disk usage is too high.")

        return round(cpu_usage_percent / 100, 4)

    def memory_usage(self) -> float:
        "Read RPi memory usage"

        memory_usage_percent = psutil.virtual_memory().percent
        self.logger.debug(f"{memory_usage_percent} % total memory usage")
        if memory_usage_percent > 80:
            self.logger.warning(
                f"memory usage is very high ({memory_usage_percent} %)",
                forward=True,
            )

        return round(memory_usage_percent / 100, 4)

    def modem(self) -> sensor_types.ModemData:
        """Read the modem, all values None on failure: it must never stop the controller."""
        try:
            modem: sensor_types.ModemData = self.hardware_interface.modem.read()
            return modem
        except Exception as e:
            self.logger.warning(f"Could not read modem: {e}")
            return sensor_types.ModemData()

    def mainboard_sensor(self) -> Any:

        mainboard_sensor = self.hardware_interface.mainboard_sensor.read()

        self.logger.debug(
            f"mainboard temp. = {mainboard_sensor.temperature} °C")

        if (mainboard_sensor.temperature
                is not None) and (mainboard_sensor.temperature > 70):
            self.logger.warning(
                f"mainboard temperature is very high ({mainboard_sensor.temperature} °C)",
                forward=True,
            )

        return mainboard_sensor
