import json
from os import path
from typing import Any

import utils
from modules import docker_client as dockerc
from modules.logging import info, debug, error
from utils.paths import GATEWAY_DATA_PATH


def on_msg_check_for_config_update(msg_payload: Any) -> bool:
    controller_config = utils.misc.get_maybe(msg_payload, "controller_config") or utils.misc.get_maybe(msg_payload, "shared", "controller_config")
    config_path = path.join(GATEWAY_DATA_PATH, "config.json")

    if controller_config is None:
        return False

    info("Controller config received!")

    # Attempt to read existing config from data folder
    try:
        with open(config_path, "r") as f:
            existing_config_file = f.read()
            existing_config = json.loads(existing_config_file)
    except json.JSONDecodeError:
        error("Failed to parse existing config file")
        existing_config = {}
    except FileNotFoundError:
        error("No existing config file found")
        existing_config = {}

    # Print existing config
    debug(f"Existing config: {existing_config}")

    # Compare existing config with new config
    if json.dumps(existing_config) == json.dumps(controller_config):
        info("Config is up to date")
    else:
        info("Config is outdated, updating...")

        docker_client = dockerc.GatewayDockerClient()
        info("Stopping controller docker container...")
        docker_client.stop_controller()

        info("Writing new config to file...")
        with open(config_path, "w") as f:
            f.write(json.dumps(controller_config, indent=4))

        info("New config written!"
              "\nController will restart in next main loop iteration.")
    return True