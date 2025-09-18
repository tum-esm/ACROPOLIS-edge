import json
from modules.logging import info, error
from typing import Any
from modules.file_writer import GatewayFileWriter
from modules.mqtt import GatewayMqttClient
from on_mqtt_msg.check_for_file_hashes_update import FILE_HASHES_TB_KEY

from utils.misc import get_maybe, get_instance_maybe

content_encodings = [None, "base64", "text", "json"]

def on_msg_check_for_files_definition_update(msg_payload: Any) -> bool:
    files = get_instance_maybe(
        dict,
        get_maybe(msg_payload, "shared", "FILES"),
        get_maybe(msg_payload, "FILES")
    )

    if files is None:
        return False

    info("Files definitions received.")
    try:
        for file_id in files:
            if not isinstance(get_maybe(files,file_id), dict):
                error("Invalid files update received")
                return False

            if not isinstance(get_maybe(files,file_id, "path"), str):
                error("Invalid files update received, missing 'path' property")
                return False

            if get_maybe(files,file_id, "encoding") not in content_encodings:
                error("Invalid files update received, unsupported 'encoding' property: " + get_maybe(files,file_id, "encoding"))
                return False

            if get_maybe(files,file_id, "create_if_not_exist") not in [None, True, False]:
                error("Invalid files update received, optional 'create_if_not_exist' property must be a boolean")
                return False

            if get_maybe(files,file_id, "restart_controller_on_change") not in [None, True, False]:
                error("Invalid files update received, optional 'restart_controller_on_change' property must be a boolean")
                return False

        GatewayFileWriter().set_files(files)
        GatewayMqttClient().request_attributes({"clientKeys": FILE_HASHES_TB_KEY})

    except json.JSONDecodeError:
        error("Failed to parse files definition")
    except Exception as e:
        error(f"Failed to update files definition: {e}")

    return True