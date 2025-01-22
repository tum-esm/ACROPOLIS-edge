import os
import time
import subprocess
from datetime import datetime, timedelta


def is_connected() -> bool:
    """Check if the Raspberry Pi is connected to the internet."""
    try:
        # Ping a reliable external host (Google's public DNS server)
        subprocess.check_call(["ping", "-c", "1", "8.8.8.8"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def monitor_and_reboot_on_disconnection(check_interval: int = 60,
                                        max_disconnection_time: int = 86400
                                        ) -> None:
    """
    Monitor the internet connection and reboot if disconnected for 24 hours.

    :param check_interval: Time in seconds between checks (default: 60 seconds).
    :param max_disconnection_time: Maximum disconnection duration in seconds (default: 24 hours = 86400 seconds).
    """
    disconnection_start: datetime = None

    while True:
        if is_connected():
            print(f"[{datetime.now()}] Internet connection is active.")
            disconnection_start = None  # Reset disconnection timer
        else:
            print(f"[{datetime.now()}] No internet connection.")
            if disconnection_start is None:
                disconnection_start = datetime.now(
                )  # Record the start time of disconnection
            elif datetime.now() - disconnection_start >= timedelta(
                    seconds=max_disconnection_time):
                print(
                    f"[{datetime.now()}] Internet has been down for 24 hours. Triggering reboot."
                )
                os.system("sudo reboot")  # Trigger reboot
                break  # This line won't be reached as the system will reboot

        time.sleep(check_interval)


if __name__ == "__main__":
    try:
        monitor_and_reboot_on_disconnection()
    except KeyboardInterrupt:
        print("Monitoring stopped.")
