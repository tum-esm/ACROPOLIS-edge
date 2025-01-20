import os
import sys
import signal
import time
from pathlib import Path
from typing import Any
from datetime import datetime
import pytz

# Ensure the project root is added to the Python path to allow absolute imports from src
sys.path.insert(0, str(Path(__file__).parent))

from interfaces import config_interface, logging_interface, state_interface, hardware_interface
from procedures import calibration, measurement, system_check
from utils import alarms, expontential_backoff, system_info

SW_VERSION = os.environ.get("ACROPOLIS_SW_VERSION", "unknown")


def run() -> None:
    """Entry point for the measurement automation
    INIT
    - Initialize Config, Logger, State, Hardware Interface
    - Initialize Procedures (System Checks, Measurement, Calibration)

    RUN INFINITE MAIN LOOP
    - Procedure: System Check
    - Procedure: Calibration
    - Procedure: Measurements (CO2, Wind)
    """

    try:
        config = config_interface.ConfigInterface.read()
    except Exception as e:
        raise e

    logger = logging_interface.Logger(config=config, origin="main")
    logger.horizontal_line()

    logger.info(
        f"Started new automation process with SW version {SW_VERSION} and PID {os.getpid()}.",
        forward=True,
    )

    logger.info(
        f"Local time is: {datetime.now().astimezone(pytz.timezone(config.local_time_zone))}",
        forward=True)

    # -------------------------------------------------------------------------

    # check and provide valid state file
    state_interface.StateInterface.init(config=config)

    # define timeouts for parts of the automation
    max_setup_time = 180
    max_system_check_time = 180
    max_calibration_time = ((len(config.calibration.gas_cylinders) + 1) *
                            config.calibration.sampling_per_cylinder_seconds +
                            300  # flush time
                            + 180  # extra time
                            )
    max_measurement_time = config.measurement.procedure_seconds + 180  # extra time
    alarms.set_alarm(max_setup_time, "setup")

    # Exponential backoff time
    ebo = expontential_backoff.ExponentialBackOff()

    # -------------------------------------------------------------------------
    # initialize all hardware interfaces
    # tear down hardware on program termination

    logger.info("Initializing hardware interfaces.", forward=True)

    try:
        hardware = hardware_interface.HardwareInterface(config=config)
    except Exception as e:
        logger.exception(e,
                         label="Could not initialize hardware interface.",
                         forward=True)
        raise e

    # tear down hardware on program termination
    def _graceful_teardown(*_args: Any) -> None:
        alarms.set_alarm(10, "graceful teardown")

        logger.info("Starting graceful teardown.")
        hardware.teardown()
        logger.info("Finished graceful teardown.")
        exit(0)

    signal.signal(signal.SIGINT, _graceful_teardown)
    signal.signal(signal.SIGTERM, _graceful_teardown)
    logger.info("Established graceful teardown hook.")

    # -------------------------------------------------------------------------
    # initialize procedures

    # initialize procedures interacting with hardware:
    #   system_check:   logging system statistics and reporting hardware/system errors
    #   calibration:    using the two reference gas bottles to calibrate the CO2 sensor
    #   measurements:   do regular measurements for x minutes

    logger.info("Initializing procedures.", forward=True)

    try:
        system_check_procedure = system_check.SystemCheckProcedure(
            config=config, hardware_interface=hardware)
        calibration_procedure = calibration.CalibrationProcedure(
            config=config, hardware_interface=hardware)
        measurement_procedure = measurement.MeasurementProcedure(
            config=config, hardware_interface=hardware)

    except Exception as e:
        logger.exception(e,
                         label="could not initialize procedures",
                         forward=True)
        raise e

    # -------------------------------------------------------------------------
    # infinite mainloop

    logger.info("Successfully finished setup, starting mainloop.",
                forward=True)

    last_successful_mainloop_iteration_time = 0.0
    while True:
        try:
            logger.info("Starting mainloop iteration.")

            # -----------------------------------------------------------------
            # SYSTEM CHECKS

            alarms.set_alarm(max_system_check_time, "system check")

            logger.info("Running system checks.")
            system_check_procedure.run()

            # -----------------------------------------------------------------
            # CALIBRATION

            alarms.set_alarm(max_calibration_time, "calibration")

            if config.active_components.run_calibration_procedures:
                if calibration_procedure.is_due():
                    logger.info("Running calibration procedure.", forward=True)
                    calibration_procedure.run()
                else:
                    logger.info("Calibration procedure is not due.")
            else:
                logger.info("Skipping calibration procedure due to config.")

            # -----------------------------------------------------------------
            # MEASUREMENTS

            alarms.set_alarm(max_measurement_time, "measurement")

            # if messages are empty, run regular measurements
            logger.info("Running measurements.")
            measurement_procedure.run()

            # -----------------------------------------------------------------

            logger.info("Finished mainloop iteration.")
            last_successful_mainloop_iteration_time = time.time()

        except Exception as e:
            logger.exception(e, label="exception in mainloop", forward=True)

            # cancel the alarm for too long mainloops
            signal.alarm(0)

            # reboot if exception lasts longer than 12 hours
            if (time.time() -
                    last_successful_mainloop_iteration_time) >= 86400:
                if system_info.read_os_uptime() >= 86400:
                    logger.info(
                        "Rebooting because no successful mainloop iteration for 24 hours.",
                        forward=True,
                    )
                    os.system("sudo reboot")
                else:
                    logger.info(
                        "Persistent issue present. Last reboot is less than 24h ago. No action."
                    )

            try:
                # check timer with exponential backoff
                if time.time() > ebo.next_try_timer():
                    ebo.set_next_timer()
                    # reinitialize all hardware interfaces
                    logger.info("Performing hardware reset.", forward=True)
                    hardware.reinitialize(config)
                    logger.info("Hardware reset was successful.", forward=True)

            except Exception as e:
                logger.exception(
                    e,
                    label="exception during hard reset of hardware",
                    forward=True,
                )
                hardware.teardown()
                exit(1)


if __name__ == "__main__":
    run()
