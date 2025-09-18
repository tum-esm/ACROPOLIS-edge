import json

from modules.docker_client import GatewayDockerClient
from modules.file_writer import GatewayFileWriter, write_file_content_to_client_attribute
from modules.logging import info, error
from typing import Any

from modules.mqtt import GatewayMqttClient
from on_mqtt_msg.check_for_file_hashes_update import FILE_HASHES_TB_KEY
from utils.misc import file_exists, get_maybe

FILE_CONTENT_PREFIX = "FILE_CONTENT_"

def on_msg_check_for_file_content_update(msg_payload: Any) -> bool:
    payload = get_maybe(msg_payload, "shared") or msg_payload
    file_id = None
    for key in payload:
        if key.startswith(FILE_CONTENT_PREFIX):
            file_id = key.replace(FILE_CONTENT_PREFIX, "")
            break
    if file_id is None:
        return False

    files_definitions = GatewayFileWriter().get_files()
    if file_id not in files_definitions:
        error(f"File definition for {file_id} not found")
        return False
    file_definition = files_definitions[file_id]

    input_file_content = get_maybe(payload, FILE_CONTENT_PREFIX + file_id)
    if input_file_content is None:
        error("Invalid file content update received")
        return False

    # encode file content to bytes based on content encoding (defaults to "text")
    file_encoding = get_maybe(file_definition, "encoding") or "text"
    if file_encoding == "json":
        if isinstance(input_file_content, dict):
            file_content = json.dumps(input_file_content)
            file_content = file_content.encode("utf-8")
        else:
            error(f"Invalid file content for {file_id}, expected JSON object")
            return False
    elif file_encoding == "base64":
        import base64
        if isinstance(input_file_content, str):
            try:
                file_content = base64.b64decode(input_file_content)
            except Exception as e:
                error(f"Failed to decode base64 content for {file_id}: {e}")
                return False
        else:
            error(f"Invalid file content for {file_id}, expected base64 string")
            return False
    elif file_encoding == "text":
        if isinstance(input_file_content, str):
            # encode as utf-8 bytes
            file_content = input_file_content.encode("utf-8")
        else:
            error(f"Invalid file content for {file_id}, expected text string")
            return False
    else:
        error(f"Unknown content encoding for {file_id}: {file_encoding}")
        return False

    file_write_version = get_maybe(file_definition, "write_version")
    file_path = GatewayFileWriter().expand_file_path(get_maybe(file_definition, "path"))
    create_if_not_exist = get_maybe(file_definition, "create_if_not_exist") in [None, True, "True"]
    restart_controller_on_change = get_maybe(file_definition, "restart_controller_on_change") in [True, "True"]

    # check if file already exists, if not, check if it should be created
    if file_exists(file_path) or create_if_not_exist:
        info(f"Writing file {file_id} at path: {file_path}")
        try:
            # write content to file
            with open(file_path, "wb") as f:
                f.write(file_content)
            # calculate new file hash and update it to ThingsBoard
            file_content_hash = GatewayFileWriter().calc_file_hash(file_path)
            file_hashes = GatewayFileWriter().get_tb_file_hashes()
            if file_hashes is None:
                error(f"File hashes are not available, cannot update hash for {file_id}")
            else:
                old_hash = get_maybe(file_hashes, file_id, "hash")
                file_hashes[file_id] = {"hash": file_content_hash}
                if file_write_version not in [None, ""]:
                    file_hashes[file_id]["write_version"] = file_write_version
                GatewayMqttClient().publish_message_raw("v1/devices/me/attributes", json.dumps({
                    FILE_HASHES_TB_KEY: file_hashes
                }))
                GatewayFileWriter().set_tb_hashes(file_hashes)

                # update file content READ attribute
                if old_hash != file_content_hash:
                    info(f"File {file_id} content updated, updating attribute")
                    write_file_content_to_client_attribute(file_id, input_file_content)
                    GatewayFileWriter().did_file_change(file_path) # update internal state
                    if restart_controller_on_change:
                        info(f"Restarting controller due to file content change")
                        GatewayDockerClient().stop_controller()
                else:
                    info(f"File {file_id} content unchanged, not updating attribute")

            # request file definitions again to verify everything is correct
            GatewayMqttClient().request_attributes({"sharedKeys": f"FILES"})
        except Exception as e:
            error(f"Failed to create file {file_id} at path {file_path}: {e}")
            return True
    else:
        error(f"File {file_id} does not exist at path: {file_path} and 'create_if_not_exist' is set to false")
        return True

    return True