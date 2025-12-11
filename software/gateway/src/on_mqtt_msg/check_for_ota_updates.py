import utils
from modules import docker_client as dockerc
from typing import Optional, Any

from modules.logging import info
from utils.misc import get_maybe


def on_msg_check_for_ota_update(msg_payload: Optional[Any]) -> bool:
    sw_title = get_maybe(msg_payload, "sw_title") or get_maybe(msg_payload, "shared", "sw_title") or get_maybe(msg_payload, "sf_title") or get_maybe(msg_payload, "shared", "sf_title")
    sw_version = get_maybe(msg_payload, "sw_version") or get_maybe(msg_payload, "shared", "sw_version") or get_maybe(msg_payload, "sf_version") or get_maybe(msg_payload, "shared", "sf_version")
    if sw_version is None:
        return False

    docker_client = dockerc.GatewayDockerClient()
    if docker_client.is_controller_running():
        current_version = docker_client.get_controller_version()
        if current_version is None or current_version != sw_version:
            info("Software update available: " + (sw_title or "?") + " from " + (
                        current_version or "UNKNOWN") + " to " + sw_version)
            docker_client.start_controller_safely(sw_version)
        else:
            info("Software is up to date (version '" + current_version + "')")
            docker_client.set_last_launched_controller_version(current_version)
    else:
        info("Launching latest edge-software: " + sw_version + " (" + (sw_title or "?") + ")")
        docker_client.start_controller_safely(sw_version)
    return True