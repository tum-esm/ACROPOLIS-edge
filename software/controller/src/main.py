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

from interfaces import config_interface, logging_interface, state_interface, hardware_interface, communication_queue
from procedures import calibration, measurement, system_check
from utils import alarms, expontential_backoff

SW_VERSION = os.environ.get("ACROPOLIS_SW_VERSION", "unknown")

# -------------------------------------------------------------------------
# initialize interfaces

# initialize communication queue
queue = communication_queue.CommunicationQueue()

# initialize config
try:
    config = config_interface.ConfigInterface.read()
except Exception as e:
    raise e


# initialize and check validity of state file
state_interface.StateInterface.init()

# initialize logger
logger = logging_interface.Logger(config=config,
                                  communication_queue=queue,
                                  origin="main")

logger.horizontal_line()
logger.info(
    f"Started new automation process with SW version {SW_VERSION} and PID {os.getpid()}.",
    forward=True,
)

logger.info(
    f"Local time is: {datetime.now().astimezone(pytz.timezone(config.local_time_zone))}",
    forward=True)

logger.info(f"Started with config: {config.dict()}", forward=True)

# check if the controller is activated in the config
if config.active_components.run_controller is False:
    while True:
        logger.info(f"Controller is not activated in the config. Waiting for new config.",
                forward=True)
        time.sleep(3600)  # sleep for 1 hour

# initialize all hardware interface
logger.info("Initializing hardware interfaces.", forward=True)

try:
    hardware = hardware_interface.HardwareInterface(config=config,
                                                    communication_queue=queue)
except Exception as e:
    logger.exception(e,
                     label="Could not initialize hardware interface.",
                     forward=True)
    raise e

# -------------------------------------------------------------------------

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


# initialize graceful teardown
def _graceful_teardown(*_args: Any) -> None:
    alarms.set_alarm(10, "graceful teardown")
    logger.info("Received termination signal. Starting graceful teardown.",
                forward=True)

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
        config=config, communication_queue=queue, hardware_interface=hardware)
    calibration_procedure = calibration.CalibrationProcedure(
        config=config, communication_queue=queue, hardware_interface=hardware)
    measurement_procedure = measurement.MeasurementProcedure(
        config=config, communication_queue=queue, hardware_interface=hardware)
except Exception as e:
    logger.exception(e, label="Could not initialize procedures", forward=True)
    raise e

# -------------------------------------------------------------------------
# infinite mainloop

logger.info("Successfully finished setup. Starting main loop.", forward=True)

while True:
    try:

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
            logger.info("Calibration procedure is not activated.")

        # -----------------------------------------------------------------
        # MEASUREMENTS

        alarms.set_alarm(max_measurement_time, "measurement")

        logger.info("Running measurements.")
        measurement_procedure.run()

        # -----------------------------------------------------------------

        logger.info("Finished mainloop iteration.")

    except Exception as e:
        logger.exception(e, label="exception in mainloop", forward=True)

        # cancel the alarm for too long mainloops
        signal.alarm(0)

        try:
            if time.time() > ebo.next_try_timer():
                ebo.set_next_timer()
                # reinitialize all hardware interfaces
                logger.info("Performing hardware reset.", forward=True)
                hardware.reinitialize(config)
                logger.info("Hardware reset was successful.", forward=True)

        except Exception as e:
            logger.exception(
                e,
                label="Exception during hard reset of hardware",
                forward=True,
            )
