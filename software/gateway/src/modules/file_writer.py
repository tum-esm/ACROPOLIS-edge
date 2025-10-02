import json
from hashlib import md5
from typing import Optional, Any

from modules.mqtt import GatewayMqttClient
from modules.logging import debug, info, error
from utils.paths import CONTROLLER_DATA_PATH

singleton_instance : Optional["GatewayFileWriter"] = None


def write_file_content_to_client_attribute(file_identifier: str, file_content: str) -> None:
    GatewayMqttClient().publish_message_raw("v1/devices/me/attributes", json.dumps({("FILE_READ_" + file_identifier): file_content}))


class GatewayFileWriter:
    files: Optional[dict] = None
    hashes: dict[str, str] = {}
    tb_hashes: Optional[dict] = None

    def __init__(self) -> None:
        global singleton_instance
        if singleton_instance is None:
            debug("[FILE-WRITER] Initializing GatewayFileWriter")
            super().__init__()
            singleton_instance = self

    # Singleton pattern
    def __new__(cls: Any) -> Any:
        global singleton_instance
        if singleton_instance is not None:
            return singleton_instance
        return super(GatewayFileWriter, cls).__new__(cls)

    def expand_file_path(self, file_path: Optional[str]) -> Optional[str]:
        if file_path is None:
            return None

        return ((file_path.replace("%DATA_PATH%", CONTROLLER_DATA_PATH)
            .replace("$DATA_PATH$", CONTROLLER_DATA_PATH))
            .replace("$DATA_PATH", CONTROLLER_DATA_PATH))


    def set_files(self, files: dict) -> None:
        self.files = files

    def set_tb_hashes(self, hashes: dict) -> None:
        self.tb_hashes = hashes

    # Read raw file contents into bytes array
    def read_file_raw(self, file_path: str) -> bytes | None:
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
                file_hash = md5(file_content).hexdigest()
                if file_path not in self.hashes:
                    self.hashes[file_path] = file_hash
                return file_content
        except FileNotFoundError:
            return None

    # Read file contents into string
    def read_file(self, file_path: str, file_encoding: str) -> str | None:
        file_content = self.read_file_raw(file_path)
        if file_content is None:
            return None

        if file_encoding == "text" or file_encoding == "json":
            return file_content.decode("utf-8")
        elif file_encoding == "base64":
            import base64
            return base64.b64encode(file_content).decode("utf-8")
        else:
            error(f"Unknown file encoding: {file_encoding}, defaulting to text")
            return file_content.decode("utf-8")

    def calc_file_hash(self, path: str) -> str:
        file_content = self.read_file_raw(path)
        if file_content is None:
            return "E_NOFILE"
        return md5(file_content).hexdigest()

    def did_file_change(self, path: str) -> bool:
        file_hash = self.calc_file_hash(path)
        if path not in self.hashes:
            self.hashes[path] = file_hash
            return False
        if file_hash != self.hashes[path]:
            self.hashes[path] = file_hash
            return True
        return False

    def get_files(self) -> dict:
        if self.files is None:
            raise Exception("Files definition is not available")
        return self.files

    def get_tb_file_hashes(self) -> Optional[dict]:
        return self.tb_hashes
