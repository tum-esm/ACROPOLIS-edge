import json
import os

from custom_types import state_types, config_types
from interfaces import logging_interface

DATA_PATH = os.path.join(os.environ.get("ACROPOLIS_DATA_PATH", "unknown"))
if DATA_PATH == "unknown":
    raise FileNotFoundError(f"Data path {DATA_PATH} does not exist.")
else:
    STATE_PATH = os.path.join(DATA_PATH, "state.json")


class StateInterface:

    @staticmethod
    def init(config: config_types.Config) -> None:
        """create state file if it does not exist yet,
        add upgrade time if missing"""
        pass

    @staticmethod
    def read(config: config_types.Config) -> state_types.State:
        logger = logging_interface.Logger(config=config,
                                          origin="state-interface")
        try:
            with open(STATE_PATH, "r") as f:
                return state_types.State(**json.load(f))
        except FileNotFoundError:
            logger.warning("state.json is missing, creating a new one")
        except Exception as e:
            logger.warning(f"state.json is invalid, creating a new one: {e}")

        new_empty_state = state_types.State(last_calibration_attempt=None,
                                            current_config_revision=0,
                                            next_calibration_cylinder=0,
                                            sht45_humidity_offset=0.0)
        StateInterface.write(new_empty_state)
        return new_empty_state

    @staticmethod
    def write(new_state: state_types.State) -> None:
        with open(STATE_PATH, "w") as f:
            json.dump(new_state.dict(), f)
