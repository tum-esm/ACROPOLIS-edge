from typing import Optional
import dataclasses

# validation is only necessary for external sources
# internal source will be covered by mypy

# Sensor data


@dataclasses.dataclass
class CO2SensorData():
    raw: float
    compensated: float
    filtered: float
    temperature: float


@dataclasses.dataclass
class BME280SensorData():
    """units: °C for temperature, rH for humidity, hPa for pressure"""

    temperature: Optional[float]
    humidity: Optional[float]
    pressure: Optional[float]


@dataclasses.dataclass
class SHT45SensorData():
    """units: °C for temperature, rH for humidity"""

    temperature: Optional[float]
    humidity: Optional[float]


@dataclasses.dataclass
class ModemData():
    """units: dBm for rssi and rsrp, dB for rsrq and sinr"""

    rssi_dbm: Optional[float] = None
    rsrp_dbm: Optional[float] = None
    rsrq_db: Optional[float] = None
    sinr_db: Optional[float] = None
    rat: Optional[str] = None
    band: Optional[str] = None
    operator: Optional[str] = None
    iccid: Optional[str] = None
    imei: Optional[str] = None


@dataclasses.dataclass
class UPSSensorData():
    ups_powered_by_grid: bool | float
    ups_battery_is_fully_charged: bool | float
    ups_battery_error_detected: bool | float
    ups_battery_above_voltage_threshold: bool | float


@dataclasses.dataclass
class WindSensorData():
    direction_min: float
    direction_avg: float
    direction_max: float
    speed_min: float
    speed_avg: float
    speed_max: float
    last_update_time: float


@dataclasses.dataclass
class WindSensorStatus():
    temperature: float
    heating_voltage: float
    supply_voltage: float
    reference_voltage: float
    last_update_time: float
