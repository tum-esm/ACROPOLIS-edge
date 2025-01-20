import os
from time import sleep
from typing import Any, Optional

import docker

from modules.git_client import GatewayGitClient
from modules.mqtt import GatewayMqttClient
from utils.paths import ACROPOLIS_GATEWAY_GIT_PATH, ACROPOLIS_DATA_PATH, ACROPOLIS_CONTROLLER_LOGS_PATH

CONTROLLER_CONTAINER_NAME = "acropolis_edge_controller"
CONTROLLER_IMAGE_PREFIX = "acropolis-edge-controller-"


class GatewayDockerClient:
    instance = None
    last_launched_version = None

    def __init__(self):
        if self.__class__.instance is None:
            print("[DOCKER-CLIENT] Initializing GatewayDockerClient")
            self.__class__.instance = self

            self.docker_client = docker.from_env()

    # Singleton pattern
    def __new__(cls):
        if hasattr(cls, 'instance') and cls.instance is not None:
            return cls.instance
        return super(GatewayDockerClient, cls).__new__(cls)

    def is_edge_running(self) -> Any:
        containers = self.docker_client.containers.list()
        for container in containers:
            if container.name == CONTROLLER_CONTAINER_NAME:
                return container.attrs["State"]["Running"]

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
                        return version
        return None

    def stop_edge(self) -> None:
        if self.is_edge_running():
            containers = self.docker_client.containers.list()
            for container in containers:
                if container.name == CONTROLLER_CONTAINER_NAME:
                    container.stop(timeout=60)
                    print(
                        "[DOCKER-CLIENT] Stopped Acropolis Edge Controller container"
                    )
        else:
            print(
                "[DOCKER-CLIENT] Acropolis Edge Controller container is not running"
            )

    def prune_containers(self) -> None:
        self.docker_client.containers.prune()
        print("[DOCKER-CLIENT] Pruned containers")

    def start_controller(self, version_to_launch: Optional[str] = None):
        if self.is_edge_running():
            current_version = self.get_edge_version()
            if current_version is None or current_version != version_to_launch:
                self.stop_edge()
                self.start_controller(version_to_launch)
            else:
                print(
                    "[DOCKER-CLIENT] Software already running with version " +
                    version_to_launch)
                self.last_launched_version = current_version
            return

        if version_to_launch is None:
            if self.last_launched_version is None:
                print(
                    "[DOCKER-CLIENT][WARN] No version specified and no previous version available, launching latest build"
                )
                version_to_launch = "unknown"
            else:
                version_to_launch = self.last_launched_version

        image_tag = CONTROLLER_IMAGE_PREFIX + version_to_launch + ":latest"

        # edge container is not running
        # check if the image is available already, if not build it
        if not self.is_image_available(image_tag):
            print("[DOCKER-CLIENT][FATAL] Image '" + image_tag +
                  "' not available")
            if version_to_launch == "unknown":
                print(
                    "[DOCKER-CLIENT][FATAL] No previous version available to build from"
                )
                print(
                    "[DOCKER-CLIENT][FATAL] Requesting version from ThingsBoard..."
                )
                GatewayMqttClient.instance().publish(
                    'v1/devices/me/attributes/request/1',
                    '{"sharedKeys":"sw_title,sw_url,sw_version"}')
                print("[DOCKER-CLIENT][FATAL] Delaying main loop by 30s...")
                sleep(
                    30
                )  # it is unlikely that the version to build will be available immediately
                return
            print("[DOCKER-CLIENT] Building image for version '" +
                  version_to_launch + "'")
            GatewayGitClient().execute_fetch()
            commit_hash = GatewayGitClient().get_commit_from_hash_or_tag(
                version_to_launch)
            if commit_hash is None:
                print(
                    "[DOCKER-CLIENT][FATAL] Unable to get commit hash for version '"
                    + version_to_launch + "'")
                return
            print("[DOCKER-CLIENT] Building image for commit " + commit_hash)

            if GatewayGitClient().execute_reset_to_commit(commit_hash) \
                and GatewayGitClient().get_current_commit() == commit_hash:
                print("[DOCKER-CLIENT] Successfully reset to commit " +
                      commit_hash)
            else:
                print("[DOCKER-CLIENT][FATAL] Unable to reset to commit " +
                      commit_hash)
                return
            build_result = self.docker_client.images.build(
                path=os.path.join(os.path.dirname(ACROPOLIS_GATEWAY_GIT_PATH),
                                  "software/controller"),
                dockerfile="./docker/Dockerfile",
                tag=CONTROLLER_IMAGE_PREFIX + version_to_launch + ":latest")
            print("[DOCKER-CLIENT] Built image for commit " + commit_hash +
                  " with tag " + CONTROLLER_IMAGE_PREFIX + version_to_launch)
            if build_result[0].tag(
                    str(CONTROLLER_IMAGE_PREFIX + "unknown:latest")):
                print('[DOCKER-CLIENT] Tagged image with "' +
                      CONTROLLER_IMAGE_PREFIX + ':latest"')
            else:
                print(f'[DOCKER-CLIENT][WARN] Unable to tag image with "' +
                      CONTROLLER_IMAGE_PREFIX + ':latest"')

        if version_to_launch == "unknown":
            print(
                "[DOCKER-CLIENT][FATAL] Version to launch is 'unknown', requesting version from ThingsBoard..."
            )
            GatewayMqttClient.instance().publish(
                'v1/devices/me/attributes/request/1',
                '{"sharedKeys":"sw_title,sw_url,sw_version"}')

        # remove old containers and start the new one
        self.last_launched_version = version_to_launch
        self.prune_containers()
        self.docker_client.containers.run(image_tag,
                                          detach=True,
                                          name=CONTROLLER_CONTAINER_NAME,
                                          restart_policy={
                                              "Name": "always",
                                              "MaximumRetryCount": 0
                                          },
                                          privileged=True,
                                          network_mode="host",
                                          environment={
                                              "ACROPOLIS_DATA_PATH":
                                              "/root/data",
                                              "ACROPOLIS_LOG_TO_CONSOLE":
                                              1,
                                              "ACROPOLIS_SW_VERSION":
                                              version_to_launch
                                          },
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
                                              ACROPOLIS_DATA_PATH: {
                                                  "bind": "/root/data",
                                                  "mode": "rw"
                                              },
                                              ACROPOLIS_CONTROLLER_LOGS_PATH: {
                                                  "bind": "/root/logs",
                                                  "mode": "rw"
                                              },
                                          })
        print(
            "[DOCKER-CLIENT] Started Acropolis Edge container with version '" +
            version_to_launch + "'")
