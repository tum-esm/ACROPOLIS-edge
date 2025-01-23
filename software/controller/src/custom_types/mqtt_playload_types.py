import dataclasses
from typing import Optional, Literal


@dataclasses.dataclass
class MQTTLogMessage():
    """message body which is sent to server"""

    severity: Literal["INFO", "WARNING", "ERROR"]
    message: str


@dataclasses.dataclass
class MQTTCO2Data():
    gmp343_raw: float
    gmp343_compensated: float
    gmp343_filtered: float
    gmp343_temperature: Optional[float]
    bme280_temperature: Optional[float]
    bme280_humidity: Optional[float]
    bme280_pressure: Optional[float]
    sht45_temperature: Optional[float]
    sht45_humidity: Optional[float]


@dataclasses.dataclass
class MQTTCO2CalibrationData():
    cal_bottle_id: int
    cal_gmp343_raw: float
    cal_gmp343_compensated: float
    cal_gmp343_filtered: float
    cal_gmp343_temperature: Optional[float]
    cal_bme280_temperature: Optional[float]
    cal_bme280_humidity: Optional[float]
    cal_bme280_pressure: Optional[float]
    cal_sht45_temperature: Optional[float]
    cal_sht45_humidity: Optional[float]


@dataclasses.dataclass
class MQTTSystemData():
    enclosure_bme280_temperature: Optional[float]
    enclosure_bme280_humidity: Optional[float]
    enclosure_bme280_pressure: Optional[float]
    raspi_cpu_temperature: Optional[float]
    raspi_disk_usage: float
    raspi_cpu_usage: float
    raspi_memory_usage: float
    ups_powered_by_grid: bool | float
    ups_battery_is_fully_charged: bool | float
    ups_battery_error_detected: bool | float
    ups_battery_above_voltage_threshold: bool | float


@dataclasses.dataclass
class MQTTWindData():
    wxt532_direction_min: float
    wxt532_direction_avg: float
    wxt532_direction_max: float
    wxt532_speed_min: float
    wxt532_speed_avg: float
    wxt532_speed_max: float
    wxt532_last_update_time: float


@dataclasses.dataclass
class MQTTWindSensorInfo():
    wxt532_temperature: float
    wxt532_heating_voltage: float
    wxt532_supply_voltage: float
    wxt532_reference_voltage: float
    wxt532_last_update_time: float
