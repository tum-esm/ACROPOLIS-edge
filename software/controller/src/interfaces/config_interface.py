import json

from custom_types import config_types
from utils.paths import ACROPOLIS_CONTROLLER_CONFIG_PATH


class ConfigInterface:

    class FileIsMissing(Exception):
        """raised when config.json was not found"""

    class FileIsInvalid(Exception):
        """raised when config.json is not in a valid format"""

    @staticmethod
    def read() -> config_types.Config:
        try:
            with open(ACROPOLIS_CONTROLLER_CONFIG_PATH, "r") as f:
                return config_types.Config(**json.load(f))
        except FileNotFoundError:
            raise ConfigInterface.FileIsMissing()
        except json.JSONDecodeError:
            raise ConfigInterface.FileIsInvalid(
                "file not in a valid json format")
        except Exception as e:
            raise ConfigInterface.FileIsInvalid(e.args[0])
