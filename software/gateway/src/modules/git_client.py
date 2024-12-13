import subprocess

from utils.paths import ACROPOLIS_GATEWAY_GIT_PATH


class GatewayGitClient:
    # Singleton pattern
    def __new__(cls):
        if not hasattr(cls, 'instance') or cls.instance is None:
            print("[GIT-CLIENT] Initializing GatewayGitClient")
            cls.instance = super(GatewayGitClient, cls).__new__(cls)
        return cls.instance
    instance = None

    def get_commit_from_hash_or_tag(self, hash_or_tag):
        commit_for_tag = self.get_commit_for_tag(hash_or_tag)
        if commit_for_tag is not None:
            return commit_for_tag
        elif self.verify_commit_hash_or_tag_exists(hash_or_tag):
            return hash_or_tag
        else:
            return None

    def get_current_commit(self):
        try:
            return subprocess.check_output(["git", f"--git-dir={ACROPOLIS_GATEWAY_GIT_PATH}", "rev-parse", "HEAD"], encoding='utf-8').strip()
        except subprocess.CalledProcessError as e:
            print("[GIT-CLIENT] Unable to determine current commit hash: ", e, e.stderr, e.stdout)
            return None

    def get_commit_for_tag(self, tag):
        try:
            return subprocess.check_output(["git", f"--git-dir={ACROPOLIS_GATEWAY_GIT_PATH}", "rev-list", "-n 1", "tags/" + tag], encoding='utf-8').strip()
        except subprocess.CalledProcessError as e:
            print("[GIT-CLIENT] Unable to find commit hash for tag '" + tag + "': ", e, e.stderr, e.stdout)
            return None

    def verify_commit_hash_or_tag_exists(self, commit_hash):
        try:
            return (subprocess.check_output(["git", f"--git-dir={ACROPOLIS_GATEWAY_GIT_PATH}", "cat-file", "-t", commit_hash])
                    .strip() == b'commit')
        except subprocess.CalledProcessError as e:
            print("[GIT-CLIENT] Unable to verify commit hash: ", e, e.stderr, e.stdout)
            return None

    def execute_reset_to_commit(self, commit_hash):
        try:
            if subprocess.run(["git", f"--git-dir={ACROPOLIS_GATEWAY_GIT_PATH}", "reset", "--hard", commit_hash]).returncode == 0:
                return True
        except subprocess.CalledProcessError as e:
            print("[GIT-CLIENT] Unable to reset to commit hash: ", e, e.stderr, e.stdout)
            return None
        return None

    def execute_fetch(self):
        try:
            if subprocess.run(["git", f"--git-dir={ACROPOLIS_GATEWAY_GIT_PATH}", "fetch"]).returncode == 0:
                return True
        except subprocess.CalledProcessError as e:
            print("[GIT-CLIENT] Unable to fetch from remote: ", e, e.stderr, e.stdout)
            return None
        return None
