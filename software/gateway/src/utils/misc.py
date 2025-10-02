import signal
import sys
import traceback
from time import sleep
from typing import Any

from modules.logging import error

def get_maybe(dictionary, *properties) -> Any:
    """ Utility function to safely get a nested property from a dictionary.
    This is a stand-in for the dict[key] syntax that raises KeyError if the key is not found."""
    for prop in properties:
        if dictionary is None:
            return None
        dictionary = dictionary.get(prop)
    return dictionary

def get_instance_maybe(inst_type, *properties) -> Any:
    """ Utility function to safely get the first property of a specific type from a list of properties."""
    for prop in properties:
        if prop is not None and isinstance(prop, inst_type):
            return prop
    return None


def fatal_error(msg) -> None:
    # Add stacktrace to error message
    error_msg = str(msg)
    error_msg += "\n" + traceback.format_exc()

    error(f'FATAL ERROR: {error_msg}')
    sys.stdout.flush()
    sleep(1)

    # Trigger the graceful shutdown handler
    signal.raise_signal( signal.SIGINT )
    sleep(15)
    sys.exit(1)

def file_exists(path: str) -> bool:
    """Check if a file exists at the given path."""
    try:
        with open(path, 'r'):
            return True
    except FileNotFoundError:
        return False
    except Exception as e:
        error(f"Error checking if file exists at {path}: {e}")
        return False