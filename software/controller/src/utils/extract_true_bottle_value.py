import os
from typing import Optional
from .paths import PROJECT_DIR


def extract_true_bottle_value(bottle_id: int) -> Optional[float]:
    """
    Extracts the line for a given bottle_id from the calibration cylinders data.

    Parameters:
        calibration_cylinders (list): List of strings read from the file.
        bottle_id (int): The bottle ID to extract.

    Returns:
        tuple: (bottle_id, tank_reading) if found, otherwise None.
    """
    file_path = os.path.join(PROJECT_DIR, "config",
                             "calibration_cylinders.csv")
    try:
        with open(file_path, "r") as f:
            calibration_cylinders = f.readlines()
    except FileNotFoundError:
        return None

    # Skip the header
    for line in calibration_cylinders[1:]:
        # Split the line into columns
        parts = line.strip().split(",")
        current_bottle_id = int(parts[0])  # Bottle ID is the first column

        if current_bottle_id == bottle_id:
            tank_reading = float(parts[1])  # Tank reading is the second column
            return tank_reading

    return None
