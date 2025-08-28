import datetime
import os
from time import sleep
from typing import Any, Optional

import docker
from docker.types import LogConfig

from modules.git_client import GatewayGitClient
from modules.logging import debug, info, warn, error
from modules.mqtt import GatewayMqttClient
from utils.paths import GATEWAY_GIT_PATH, GATEWAY_DATA_PATH, CONTROLLER_LOGS_PATH

CONTROLLER_CONTAINER_NAME = "teg_controller"
CONTROLLER_IMAGE_PREFIX = "teg-controller-"

singleton_instance : Optional["GatewayDockerClient"] = None

class GatewayDockerClient:
    last_launched_version = None

    def __init__(self) -> None:
        global singleton_instance
        if singleton_instance is None:
            debug("[DOCKER-CLIENT] Initializing GatewayDockerClient")
            super().__init__()
            singleton_instance = self
            try:
                self.docker_client = docker.from_env()
            except Exception as e:
                error("[DOCKER-CLIENT] Failed to initialize GatewayDockerClient: {}".format(e))

    # Singleton pattern
    def __new__(cls: Any) -> Any:
        global singleton_instance
        if singleton_instance is not None:
            return singleton_instance
        return super(GatewayDockerClient, cls).__new__(cls)

    def is_edge_running(self) -> bool:
        containers = self.docker_client.containers.list()
        for container in containers:
            if container.name == CONTROLLER_CONTAINER_NAME:
                return container.attrs["State"]["Running"]
        return False

    def is_image_available(self, image_tag: str) -> bool:
        for image in self.docker_client.images.list():
            if image_tag in image.tags:
                return True
        return False

    def get_edge_version(self) -> Optional[str]:
        if self.is_edge_running():
            containers = self.docker_client.containers.list()
            for container in containers:
                if container.name == CONTROLLER_CONTAINER_NAME:
                    version = container.attrs["Config"]["Image"].split("-")[-1]
                    if version.__len__() > 0 and (version[0] == "v"
                                                  or version.__len__() == 40):
                        if version.endswith(":latest"):
                            version = version[:-7]
                        return version
        return None

    def get_edge_startup_timestamp_ms(self) -> Optional[int]:
        if self.is_edge_running():
            containers = self.docker_client.containers.list()
            for container in containers:
                if container.name == CONTROLLER_CONTAINER_NAME:
                    return int(
                        datetime.datetime.strptime(container.attrs["State"]["StartedAt"][:-4], "%Y-%m-%dT%H:%M:%S.%f" )
                        .replace(tzinfo=datetime.timezone.utc)
                        .timestamp() * 1000
                    )
        return None

    def stop_edge(self) -> None:
        if self.is_edge_running():
            containers = self.docker_client.containers.list()
            for container in containers:
                if container.name == CONTROLLER_CONTAINER_NAME:
                    if self.last_launched_version is None:
                        self.last_launched_version = self.get_edge_version()
                    container.stop(timeout=60)
                    info("[DOCKER-CLIENT] Stopped Controller container")
        else:
            info("[DOCKER-CLIENT] Controller container is not running")

    def prune_containers(self) -> None:
        self.docker_client.containers.prune()
        info("[DOCKER-CLIENT] Pruned containers")

    def start_controller(self, version_to_launch: Optional[str] = None) -> None:
        if self.is_edge_running():
            current_version = self.get_edge_version()
            if current_version is None or current_version != version_to_launch or current_version == "unknown":
                self.stop_edge()
                self.start_controller(version_to_launch)
            else:
                info("[DOCKER-CLIENT] Software already running with version " + version_to_launch)
                self.last_launched_version = current_version
            return

        if version_to_launch is None:
            if self.last_launched_version is None:
                warn("[DOCKER-CLIENT] No version specified and no previous version available, launching latest build")
                version_to_launch = "unknown"
            else:
                version_to_launch = self.last_launched_version

        image_tag : str = CONTROLLER_IMAGE_PREFIX + version_to_launch + ":latest"

        # edge container is not running
        # check if the image is available already, if not build it
        if not self.is_image_available(image_tag):
            error("[DOCKER-CLIENT] Image '" + image_tag + "' not available")
            if version_to_launch == "unknown":
                error("[DOCKER-CLIENT] No previous version available to build from")
                error("[DOCKER-CLIENT] Requesting version from ThingsBoard...")
                GatewayMqttClient().publish('v1/devices/me/attributes/request/1', '{"sharedKeys":"sw_title,sw_url,sw_version"}')
                GatewayMqttClient().publish_sw_state(
                    version_to_launch,"FAILED",
                    "No previous version available to build from, requested version info from ThingsBoard")
                error("[DOCKER-CLIENT] Delaying main loop by 30s...")
                sleep(30) # it is unlikely that the version to build will be available immediately
                return
            info("[DOCKER-CLIENT] Building image for version '" + version_to_launch + "'")
            GatewayMqttClient().publish_sw_state(version_to_launch, "DOWNLOADING")
            GatewayGitClient().execute_fetch()
            commit_hash = GatewayGitClient().get_commit_from_hash_or_tag(version_to_launch)
            if commit_hash is None:
                error("[DOCKER-CLIENT] Unable to get commit hash for version '" + version_to_launch + "'")
                return
            info("[DOCKER-CLIENT] Building image for commit " + commit_hash)

            if GatewayGitClient().execute_reset_to_commit(commit_hash) \
                and GatewayGitClient().get_current_commit() == commit_hash:
                info("[DOCKER-CLIENT] Successfully reset to commit " + commit_hash)
            else:
                error("[DOCKER-CLIENT] Unable to reset to commit " + commit_hash)
                return
            GatewayMqttClient().publish_sw_state(version_to_launch, "DOWNLOADED")
            build_result = self.docker_client.images.build(
                # TODO: make this path configurable
                path=os.path.join(os.path.dirname(GATEWAY_GIT_PATH), "software/controller"),
                dockerfile="./docker/Dockerfile",
                tag=CONTROLLER_IMAGE_PREFIX + version_to_launch + ":latest"
            )
            info("[DOCKER-CLIENT] Built image for commit " + commit_hash + " with tag " + CONTROLLER_IMAGE_PREFIX + version_to_launch)
            if build_result[0].tag(str(CONTROLLER_IMAGE_PREFIX + "unknown:latest")):
                info('[DOCKER-CLIENT] Tagged image with "' + CONTROLLER_IMAGE_PREFIX + 'unknown:latest"')
            else:
                warn(f'[DOCKER-CLIENT] Unable to tag image with "' + CONTROLLER_IMAGE_PREFIX + ':latest"')

        if version_to_launch == "unknown":
            error("[DOCKER-CLIENT][FATAL] Version to launch is 'unknown', requesting version from ThingsBoard...")
            GatewayMqttClient().publish('v1/devices/me/attributes/request/1', '{"sharedKeys":"sw_title,sw_url,sw_version"}')

        GatewayMqttClient().publish_sw_state(version_to_launch, "UPDATING")
        # remove old containers and start the new one
        self.last_launched_version = version_to_launch
        self.prune_containers()
        self.docker_client.containers.run(
            image_tag,
            detach=True,
            name=CONTROLLER_CONTAINER_NAME,
            restart_policy={
                "Name": "always",
                "MaximumRetryCount": 0
            },
            log_config=LogConfig(type=LogConfig.types.JSON, config={
                "max-size": "10m",
                "max-file": "5"
            }),
            privileged=True,
            network_mode="host",
            # TODO: forward env variables to controller (except TEG_ prefixed ones)
            #environment={
            #    "ACROPOLIS_DATA_PATH": "/root/data",
            #    "ACROPOLIS_LOG_TO_CONSOLE": "1",
            #    "ACROPOLIS_SW_VERSION": version_to_launch
            #},
            volumes={
                "/bin/vcgencmd": {
                    "bind": "/bin/vcgencmd",
                    "mode": "ro"
                },
                "/bin/uptime": {
                    "bind": "/bin/uptime",
                    "mode": "ro"
                },
                "/bin/pigs": {
                    "bind": "/bin/pigs",
                    "mode": "ro"
                },
                GATEWAY_DATA_PATH: {
                    "bind": "/root/data",
                    "mode": "rw"
                },
                # TODO: remove this volume, the data path is sufficient (see above)
                CONTROLLER_LOGS_PATH: {
                    "bind": "/root/logs",
                    "mode": "rw"
                },
            }
        )
        GatewayMqttClient().publish_sw_state(version_to_launch, "UPDATED")
        info("[DOCKER-CLIENT] Started container with version '" + version_to_launch + "'")