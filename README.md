# ACROPOLIS CO<sub>2</sub> Sensor Network
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15849217.svg)](https://doi.org/10.5281/zenodo.15849217)
[![mypy](https://github.com/tum-esm/ACROPOLIS-edge/actions/workflows/test-controller.yaml/badge.svg)](https://github.com/tum-esm/ACROPOLIS-edge/actions)
[![mypy](https://github.com/tum-esm/ACROPOLIS-edge/actions/workflows/test-gateway.yaml/badge.svg)](https://github.com/tum-esm/ACROPOLIS-edge/actions)


This repository contains the software and hardware blueprints for the measurement systems deployed at the edge of the **ACROPOLIS** (Autonomous and Calibrated Roof-top Observatory for MetroPOLItan Sensing) CO<sub>2</sub> sensor network. This initial network consists of twenty prototype systems evenly distributed across the city of Munich. The project is part of [**ICOS Cities**](https://www.icos-cp.eu/projects/icos-cities), funded by the European Union's Horizon 2020 Research and Innovation Programme under grant agreement No. **101037319**.

<br/>

## Key Features

- **Non-Expert Setup**: The software is designed for easy deployment, requiring minimal technical expertise for setup and operation.
- **Scalability**: The network infrastructure allows for seamless scaling, enabling easy expansion to a larger number of devices and locations.
- **Remote Software and Configuration Update**: Supports remote updates for software and configuration, ensuring continuous improvement and easy deployment of changes.
- **Offline Data Backup**: SQLite implementation serves as a local backup for measurement data.
- **ThingsBoard Integration**: All measurements are transmitted via MQTT to a hosted ThingsBoard instance for centralized data collection and analysis.

<br/>

## Software Components

- **Edge Controller**: An autonumous software managing sensors and actors and running within a Docker container for isolated and consistent deployment.
- **Edge Gateway**: A standalone process managing the active edge controller container version, implementing a MQTT client to act as a communication gateway, and acting as the endpoint for remote commands.

<br/>

## Repository Overview

- Docs
- Setup
- Software

<br/>

## System Overview

Each edge system is managed by a Raspberry Pi 4, utilizing an LTE hat (NB-IoT) for internet connectivity. The primary sensor is the Vaisala GMP343 CO<sub>2</sub> sensor, accompanied by auxiliary BME280 and SHT45 sensors for environmental monitoring. Airflow is regulated by a brushless membrane pump and 2/2 valves, which switch between the sampling head and calibration tanks. Additionally, a Vaisala WXT-532 wind sensor is co-located with the sampling head to monitor wind conditions. The system includes a UPS and battery backup to ensure uninterrupted operation.

<br/>

## Software Architecture

<img src="docs/pictures/ACROPOLIS-Architecture.svg">

<br/>

## Related Work

Aigner et. al.: Advancing Urban Greenhouse Gas Monitoring: Development and Evaluation of a High-Density CO2 Sensor Network in Munich. ICOS Science Conference 2024, Versailles, France, 10.-12. Sept, [Link](https://www.icos-cp.eu/news-and-events/science-conference/icos2024sc/all-abstracts)

<br/>

## Current Development Team:

- Patrick Aigner [@patrickjaigner](https://github.com/patrickjaigner)
- Lars Frölich [@larsfroelich](https://github.com/larsfroelich)

<br/>

## Past Development Team Members:

- Felix Böhm [@empicano](https://github.com/empicano)
- Moritz Makowski [@dostuffthatmatters](https://github.com/dostuffthatmatters)
- Adrian Schmitt
