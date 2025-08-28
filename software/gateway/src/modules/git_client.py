import subprocess
from modules.logging import debug, error
from os.path import dirname
from typing import Optional, Any

from utils.paths import GATEWAY_GIT_PATH

singleton_instance : Optional["GatewayGitClient"] = None

class GatewayGitClient:
    def __init__(self):
        global singleton_instance
        if singleton_instance is None:
            debug("[GIT-CLIENT] Initializing GatewayGitClient")
            super().__init__()
            singleton_instance = self

    # Singleton pattern
    def __new__(cls: Any) -> "GatewayGitClient":
        global singleton_instance
        if singleton_instance is not None:
            return singleton_instance
        return super(GatewayGitClient, cls).__new__(cls)

    def get_commit_from_hash_or_tag(self, hash_or_tag: str) -> Optional[str]:
        commit_for_tag = self.get_commit_for_tag(hash_or_tag)
        if commit_for_tag is not None:
            return commit_for_tag
        elif self.verify_commit_hash_or_tag_exists(hash_or_tag):
            return hash_or_tag
        else:
            return None

    def get_current_commit(self) -> Optional[str]:
        try:
            return subprocess.check_output(["git", "rev-parse", "HEAD"], encoding='utf-8', cwd=dirname(GATEWAY_GIT_PATH)).strip()
        except subprocess.CalledProcessError as e:
            error(f"[GIT-CLIENT] Unable to determine current commit hash: : {e} {e.stderr} {e.stdout}")
            return None

    def get_commit_for_tag(self, tag) -> Optional[str]:
        try:
            return subprocess.check_output(["git", "rev-list", "-n 1", "tags/" + tag], encoding='utf-8', cwd=dirname(GATEWAY_GIT_PATH)).strip()
        except subprocess.CalledProcessError as e:
            error(f"[GIT-CLIENT] Unable to find commit hash for tag '{tag}': {e} {e.stderr} {e.stdout}")
            return None

    def verify_commit_hash_or_tag_exists(self, commit_hash: str) -> bool:
        try:
            return (subprocess.check_output(["git", "cat-file", "-t", commit_hash], cwd=dirname(GATEWAY_GIT_PATH))
                    .strip() == b'commit')
        except subprocess.CalledProcessError as e:
            error(f"[GIT-CLIENT] Unable to verify commit hash: {e} {e.stderr} {e.stdout}")
            return False

    def execute_reset_to_commit(self, commit_hash: str) -> bool:
        try:
            if subprocess.run(["git", "checkout", "-f", commit_hash], cwd=dirname(GATEWAY_GIT_PATH)).returncode == 0\
                and subprocess.run(["git", "reset", "HEAD", "--hard"], cwd=dirname(GATEWAY_GIT_PATH)).returncode == 0\
                and subprocess.run(["git", "clean", "-f", "-d"], cwd=dirname(GATEWAY_GIT_PATH)).returncode == 0:
                return True
        except subprocess.CalledProcessError as e:
            error(f"[GIT-CLIENT] Unable to reset to commit hash: {e} {e.stderr} {e.stdout}")
        return False

    def execute_fetch(self) -> bool:
        try:
            if subprocess.run(["git", "fetch"], cwd=dirname(GATEWAY_GIT_PATH)).returncode == 0:
                return True
        except subprocess.CalledProcessError as e:
            error(f"[GIT-CLIENT] Unable to fetch from remote: {e} {e.stderr} {e.stdout}")
        return False
