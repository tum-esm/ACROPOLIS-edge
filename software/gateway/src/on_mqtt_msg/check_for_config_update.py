import json
from os import path
from typing import Any, Optional

import utils
from modules import docker_client as dockerc
from utils.paths import ACROPOLIS_DATA_PATH


def on_msg_check_for_config_update(msg_payload: Optional[Any]) -> bool:
    controller_config = utils.misc.get_maybe(msg_payload, "controller_config")
    config_path = path.join(ACROPOLIS_DATA_PATH, "config.json")

    if controller_config is not None:
        print("Controller config received!")

        # Attempt to read existing config from data folder
        try:
            with open(config_path, "r") as f:
                existing_config_file = f.read()
                existing_config = json.loads(existing_config_file)
        except json.JSONDecodeError:
            print("Failed to parse existing config file")
            existing_config = {}
        except FileNotFoundError:
            print("No existing config file found")
            existing_config = {}

        # Print existing config
        print("Existing config:")
        print(existing_config)

        # Compare existing config with new config
        if json.dumps(existing_config) == json.dumps(controller_config):
            print("Config is up to date")
        else:
            print("Config is outdated, updating...")

            docker_client = dockerc.GatewayDockerClient()
            print("Stopping acropolis-controller docker container...")
            docker_client.stop_edge()

            print("Writing new config to file...")
            with open(config_path, "w") as f:
                f.write(json.dumps(controller_config, indent=4))

            print("New config written!"
                  "\nController will restart in next main loop iteration.")
        return True
    return False
