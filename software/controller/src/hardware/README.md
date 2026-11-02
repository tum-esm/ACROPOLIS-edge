# Hardware

This directory contains the hardware-related implementation, including sensors, actuators, and modules that integrate these components.

## Directory Structure

```bash
📁 actuators
    📄 _base_actuator.py      # Base class for actuators
    📄 actuator_[*].py        # Specific actuator implementations
📁 modules
    📄 co2_sensor.py
    📄 heated_sensor_box.py
    📄 wind_sensor.py
📁 sensors
    📄 _base_sensor.py       # Base class for sensors
    📄 sensor_[*].py         # Specific sensor implementations
```

## Implementation Overview

The hardware components are structured using abstract base classes to ensure modularity and maintainability. The base classes provide:

- Unified logging, initialization, and teardown procedures
- Simulation capabilities for testing
- Built-in error handling and retry logic for sensor reads and actuator control
- GPIO pin factory forwarding to prevent interface conflicts

## Actuators

The `actuators` subfolder contains hardware interfaces for:

- **ACL Type 201** – Solenoid valves (24V)
- **Schwarzer Precision SP 622 EC_BL** – Membrane pump (24V)
- **DBK Enclosures** - 10W PTC heating element (24V)
- **EBM-Papst** - DC sleeve fan (24V)

## Sensors

The `sensors` subfolder includes hardware interfaces for various environmental and system sensors:

- **Bosch BME280** – Humidity, temperature, and pressure
- **Bosch BMP585** – Temperature and pressure
- **Grove MCP9808** – Temperature
- **Phoenix Contact UPS** – Uninterruptible power supply monitoring
- **Sensirion SHT45** – Humidity and temperature
- **Vaisala GMP343** – CO₂ measurement
- **Vaisala WXT532** – Wind speed and direction

## Modules

The `modules` subfolder contains higher-level modules that integrate multiple sensors and actuators:

### **CO₂ Sensor Module**:

- Interfaces with Vaisala GMP343 (CO₂ sensor)
- Integrates Sensirion SHT45 for humidity correction
- Utilizes the air-inlet pressure sensor for pressure correction: Bosch BMP585 on newer probes, Bosch BME280 on older ones (detected at startup)
- Handles CO₂ measurement, calibration, dilution correction
- Queues processed data for MQTT transmission

### **Heated Sensor Box**:

- Implements PID temperature control using Grove MCP9808
- Controls PTC heating element
- Manages ventilation with sleeve fan
- Runs in a multithreading environment for real-time response

### **Wind Sensor Module**:

- Interfaces with Vaisala WXT532 for wind speed and direction measurement
- Queues processed data for MQTT transmission

<br>

---

For further details on specific implementations, refer to the respective module and class documentation.
