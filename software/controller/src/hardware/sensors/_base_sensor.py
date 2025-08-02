from abc import ABC, abstractmethod
import time
import random
from typing import Any, Optional
try:
    import gpiozero.pins.pigpio
except Exception:
    pass

from custom_types import config_types
from interfaces import logging_interface, communication_queue


class Sensor(ABC):
    """Abstract base class for a generic sensor."""

    class SensorError(Exception):
        """Raised when an error occurs in the sensor class."""
        

    def __init__(
            self,
            config: config_types.Config,
            communication_queue: communication_queue.CommunicationQueue,
            max_retries: int = 3,
            retry_delay: float = 0.5,
            pin_factory: Optional[gpiozero.pins.pigpio.PiGPIOFactory] = None):

        # init parameters
        self.config = config
        self.communication_queue = communication_queue
        self.simulate = config.active_components.simulation_mode
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.pin_factory = pin_factory

        # init logger with sensor class name
        self.logger = logging_interface.Logger(
            communication_queue=self.communication_queue,
            config=config,
            origin=f"{self.__class__.__name__}")

        if self.simulate:
            self.logger.info(f"Simulating {self.__class__.__name__}.")
            return

        self.logger.info("Starting initialization.")
        self._initialize_sensor()
        self.logger.info("Finished initialization.")

    def read_with_retry(self,
                        timeout: float = 10,
                        reduce_logs: bool = False,
                        *args: Any,
                        **kwargs: Any) -> Any:
        """Read the sensor value with retries, passing dynamic arguments.
        Raises SimulatedValue if the sensor is in simulation mode.
        Raises SensorError if all retries fail."""

        start_time = time.time()
        for attempt in range(1, self.max_retries + 1):
            try:
                if not reduce_logs:
                    self.logger.debug(
                        f"Attempt {attempt} of {self.max_retries}: Reading sensor value."
                    )
                return self.read(*args, **kwargs)
            except Exception as e:
                self.logger.warning(f"Attempt {attempt} failed: {e}")
                if timeout and time.time() - start_time > timeout:
                    raise self.SensorError("Read retries exceeded timeout.")
                if attempt < self.max_retries:
                    self.reset_sensor()
                    self.logger.info(
                        f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.exception(
                        e, label="All retries failed. Raising exception.")
                    raise self.SensorError("All retries failed.")

    def read(self, *args: Any, **kwargs: Any) -> Any:
        """Read the sensor value and forward dynamic arguments to _read.
        Raises SimulatedValue if the sensor is in simulation mode.
        Raises SensorError if the read fails."""

        if self.simulate:
            self.logger.info("Simulating read.")
            return self._simulate_read(*args, **kwargs)

        try:
            return self._read(*args, **kwargs)

        except (BrokenPipeError, ConnectionError) as e:
            self.logger.exception(e, "Lost connection to pigpiod.")
            raise e
        except Exception as e:
            self.logger.exception(e, label="Could not read sensor data.")
            raise self.SensorError("Could not read sensor data.")

    def reset_sensor(self) -> None:
        """Reset the sensor by shutting it down and reinitializing it."""

        if self.simulate:
            self.logger.info("Simulating sensor reset.")
            return

        self.logger.info("Starting sensor shutdown.")
        self._shutdown_sensor()
        self.logger.info("Finished sensor shutdown.")
        time.sleep(1)
        self.logger.info("Starting initialization.")
        self._initialize_sensor()
        self.logger.info("Finished initialization.")
        time.sleep(1)

    def teardown(self) -> None:
        """Shutdown the sensor and close all interfaces."""
        if self.simulate:
            self.logger.info("Simulating sensor teardown.")
            return

        self.logger.info("Starting sensor teardown.")
        self._shutdown_sensor()
        self.logger.info("Finished sensor teardown.")

    def check_errors(self) -> None:
        """Check for any errors that might have occurred."""
        if self.simulate:
            self.logger.debug("No errors present in simulation mode.")
            return
        try:
            self._check_errors()
            self.logger.info("No errors detected.")
        except Exception:
            self.reset_sensor()
            self.logger.info("Errors failed. Restarting sensor.")
            time.sleep(5)

    def _check_errors(self) -> None:
        """Abstract method to check for errors. Can be overridden by subclasses."""
        pass

    def _simulate_read(self, *args: Any, **kwargs: Any) -> Any:
        """Generate a simulated read value. Can be overridden by subclasses."""
        return random.random()

    @abstractmethod
    def _initialize_sensor(self) -> None:
        """Initializes the sensor and sets up all interfaces and connections.
        Is called by the constructor and the method reset_sensor."""
        pass

    @abstractmethod
    def _shutdown_sensor(self) -> None:
        """Closes all interfaces and connections.
        Is called by the methods reset_sensor and teardown."""
        pass

    @abstractmethod
    def _read(self, *args: Any, **kwargs: Any) -> Any:
        """Returns the sensor outout.
        Needs to raise an exception if the read fails.
        Is called by the methods read and read_with_retry."""
        pass
