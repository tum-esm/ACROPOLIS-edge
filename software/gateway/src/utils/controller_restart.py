from time import time_ns, sleep

from modules.docker_client import GatewayDockerClient
from modules.logging import info, error
from modules.mqtt import GatewayMqttClient

DEFAULT_CONTAINER_RESTART_DELAY_MS = 600_000
CONTAINER_RESTART_EXPONENTIAL_BACKOFF_FACTOR = 1.6
container_restart_delay_ms = DEFAULT_CONTAINER_RESTART_DELAY_MS
last_container_restart_ts = 0

def restart_controller_if_needed():
    global container_restart_delay_ms, last_container_restart_ts

    if int(time_ns() / 1_000_000) - last_container_restart_ts > container_restart_delay_ms:
        last_container_restart_ts = int(time_ns() / 1_000_000)
        docker_client = GatewayDockerClient()
        if not docker_client.is_controller_running():
            container_restart_delay_ms *= CONTAINER_RESTART_EXPONENTIAL_BACKOFF_FACTOR
            info("Controller is not running, starting new container in 10s...")
            info("New controller restart exponential backoff: " + str(container_restart_delay_ms) + "ms")
            sleep(10)
            last_launched_version = docker_client.get_last_launched_controller_version()
            if last_launched_version is not None:
                docker_client.start_controller(last_launched_version)
                return True
            else:
                error("Failed to determine last launched controller version, unable to start new container...")
                GatewayMqttClient().request_attributes({"sharedKeys": "sw_title,sw_url,sw_version"})
                GatewayMqttClient().publish_sw_state("UNKNOWN", "FAILED",
                                                     "No previous version known to launch from, requested version info from ThingsBoard")
                error("Requested controller version from Thingsboard. Delaying main loop by 20s...")
                sleep(20)  # it is unlikely that the version to build will be available immediately
                return True
        elif container_restart_delay_ms > DEFAULT_CONTAINER_RESTART_DELAY_MS:
            info("New controller restart exponential backoff: " + str(container_restart_delay_ms) + "ms")
            container_restart_delay_ms = max(
                DEFAULT_CONTAINER_RESTART_DELAY_MS,
                int(container_restart_delay_ms / CONTAINER_RESTART_EXPONENTIAL_BACKOFF_FACTOR)
            )

    return False