import os
from os.path import dirname, abspath, join

PROJECT_DIR = dirname(dirname(dirname(abspath(__file__))))

# DATA PATH
ACROPOLIS_CONTROLLER_DATA_PATH = os.path.join(
    os.environ.get("ACROPOLIS_DATA_PATH", "unknown"))

# STATE & COMFIG PATH
if ACROPOLIS_CONTROLLER_DATA_PATH == "unknown":
    raise FileNotFoundError(
        f"Data path {ACROPOLIS_CONTROLLER_DATA_PATH} does not exist.")
else:
    ACROPOLIS_CONTROLLER_STATE_PATH = os.path.join(
        ACROPOLIS_CONTROLLER_DATA_PATH, "state.json")
    ACROPOLIS_CONTROLLER_CONFIG_PATH = os.path.join(
        ACROPOLIS_CONTROLLER_DATA_PATH, "config.json")

# LOGS PATH
if os.path.exists("/root/logs"):
    ACROPOLIS_CONTROLLER_LOGS_PATH = "/root/logs"
else:
    fallback_dir = join(PROJECT_DIR, "logs")
    os.makedirs(fallback_dir, exist_ok=True)
    ACROPOLIS_CONTROLLER_LOGS_PATH = fallback_dir
