import time
from datetime import datetime
import subprocess
import json
from utils.state_interface import StateInterface


def os_uptime_duration_seconds() -> int:
    """Reads OS system uptime from terminal and returns time in seconds.
    
    Returns the time in seconds since the last reboot of the system."""
    uptime_date = subprocess.check_output("uptime -s", shell=True)
    uptime_string = uptime_date.decode("utf-8").strip()
    uptime_datetime = datetime.strptime(uptime_string, "%Y-%m-%d %H:%M:%S")
    uptime_seconds = int(time.time() - uptime_datetime.timestamp())

    return uptime_seconds


def offline_duration_seconds() -> int:
    """Reads unix timestamps since for last failed connection attempt from state file.
    
    Returns the time in seconds since the last failed connection attempt."""
    state = StateInterface.read()
    if state.offline_timestamp is not None:
        return int(time.time()) - state.offline_timestamp
    else:
        return 0


def offline_reboot_trigger() -> bool:
    """Checks if the system should reboot due to offline state.
    
    Returns True if the system should reboot, False otherwise."""
    if offline_duration_seconds() > 86400:
        if os_uptime_duration_seconds() > 86400:
            return True
    return False
