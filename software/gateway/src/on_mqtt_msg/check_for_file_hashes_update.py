import json
import os
from modules.logging import info, error, warn
from modules.file_writer import GatewayFileWriter, write_file_content_to_client_attribute
from typing import Any
import utils
from modules.mqtt import GatewayMqttClient
from utils.misc import get_maybe

FILE_HASHES_TB_KEY = "FILE_HASHES"
def on_msg_check_for_file_hashes_update(msg_payload: Any) -> bool:
    file_hashes = utils.misc.get_maybe(msg_payload, "client", FILE_HASHES_TB_KEY)

    if file_hashes is None:
        return False

    if not isinstance(file_hashes, dict):
        error("Invalid file hashes update received")
        return False

    info("File hashes definitions received.")

    file_defs = GatewayFileWriter().get_files()
    new_hashes = {}

    for file_id in file_hashes:
        if file_id not in file_defs:
            warn(f"File {file_id} is no longer defined, removing from client attributes")
            write_file_content_to_client_attribute(file_id, "")

    for file_id in file_defs:
        file_path = GatewayFileWriter().expand_file_path(get_maybe(file_defs, file_id, "path"))
        if file_path is None:
            warn(f"File definition for {file_id} has no path, skipping")
            continue
        file_encoding = get_maybe(file_defs, file_id, "encoding") or "text"
        previous_file_hash = get_maybe(file_hashes, file_id, "hash")
        current_file_hash = GatewayFileWriter().calc_file_hash(file_path)
        new_hashes[file_id] = {
            "hash": current_file_hash,
            "write_version": get_maybe(file_defs, file_id, "write_version")
        }

        # check if the file exists and if it doesn't, if it should be created
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            if get_maybe(file_defs, file_id, "create_if_not_exist") in [None, True, "True"]:
                # if the file does not exist and should be created, request its content
                info(f"File {file_path} does not exist, requesting content update for {file_id}")
                GatewayMqttClient().request_attributes({"sharedKeys": f"FILE_CONTENT_" + file_id})
            if current_file_hash != get_maybe(file_hashes, file_id, "hash"):
                info(f"File {file_path} no longer exists. Updating attributes for id '{file_id}'")
                write_file_content_to_client_attribute(file_id, "E_NOFILE")
        else:
            # if the file exists, check its hash
            if previous_file_hash != current_file_hash:
                info(f"File {file_path} has changed, updating id '{file_id}'")
                write_file_content_to_client_attribute(file_id, GatewayFileWriter().read_file(file_path, file_encoding) or "E_EMPTYFILE")

                # request which (if) content should be written to it
                info(f"Requesting file content update for '{file_id}'")
                GatewayMqttClient().request_attributes({"sharedKeys": f"FILE_CONTENT_" + file_id})
            elif get_maybe(file_defs, file_id, "write_version") not in [None, ""]:
                # hash unchanged - check if write version has changed
                write_version_changed = get_maybe(file_defs, file_id, "write_version") != get_maybe(file_hashes, file_id, "write_version")
                if write_version_changed:
                    info(f"File {file_path} write version changed, requesting content update for {file_id}")
                    GatewayMqttClient().request_attributes({"sharedKeys": f"FILE_CONTENT_" + file_id})

    GatewayMqttClient().publish_message_raw("v1/devices/me/attributes", json.dumps({
        FILE_HASHES_TB_KEY: new_hashes
    }))
    GatewayFileWriter().set_tb_hashes(new_hashes)
    return True
