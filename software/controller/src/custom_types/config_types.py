from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ActiveComponentsConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    run_calibration_procedures: bool
    send_messages_over_mqtt: bool
    run_hardware_tests: bool


# -----------------------------------------------------------------------------


class CalibrationGasConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    valve_number: Literal[1, 2, 3, 4]
    bottle_id: str


class CalibrationConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    average_air_inlet_measurements: int = Field(..., ge=1)
    calibration_frequency_days: int = Field(..., ge=1)
    calibration_hour_of_day: int = Field(..., ge=0, le=23)
    gas_cylinders: list[CalibrationGasConfig] = Field(...,
                                                      min_length=1,
                                                      max_length=3)
    sampling_per_cylinder_seconds: int = Field(..., ge=6, le=1800)
    system_flushing_pump_pwm_duty_cycle: float = Field(ge=0, le=1)
    system_flushing_seconds: int = Field(..., ge=0, le=600)


# -----------------------------------------------------------------------------


class DocumentationConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    site_name: str
    site_short_name: str
    site_observation_since: str
    inlet_elevation: str
    last_maintenance_date: str
    maintenance_comment: str
    gmp343_sensor_id: str


# -----------------------------------------------------------------------------


class HardwareConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    pump_pwm_duty_cycle: float = Field(ge=0, le=1)
    gmp343_optics_heating: bool
    gmp343_linearisation: bool
    gmp343_temperature_compensation: bool
    gmp343_relative_humidity_compensation: bool
    gmp343_pressure_compensation: bool
    gmp343_oxygen_compensation: bool
    gmp343_filter_seconds_averaging: int = Field(..., ge=0, le=60)
    gmp343_filter_smoothing_factor: int = Field(..., ge=0, le=255)
    gmp343_filter_median_measurements: int = Field(..., ge=0, le=13)


# -----------------------------------------------------------------------------


class MeasurementConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    average_air_inlet_measurements: int
    procedure_seconds: int = Field(..., ge=10, le=7200)
    valve_number: Literal[1, 2, 3, 4]


# -----------------------------------------------------------------------------


class Config(BaseModel):
    """The config.json for each sensor"""
    model_config = ConfigDict(extra='forbid')

    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-(?:alpha|beta)\.\d+)?$"
                         )  # e.g., "1.2.3" or "99.0.1" or "42.1.0-alpha.6"
    active_components: ActiveComponentsConfig
    calibration: CalibrationConfig
    documentation: DocumentationConfig
    hardware: HardwareConfig
    measurement: MeasurementConfig
