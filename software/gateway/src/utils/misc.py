import signal
import sys
import traceback
from time import sleep

from modules.mqtt import GatewayMqttClient


def get_maybe(dictionary, *properties):
    for prop in properties:
        if dictionary is None:
            return None
        dictionary = dictionary.get(prop)
    return dictionary

def fatal_error(msg):
    # Set a timer to force exit if graceful shutdown fails
    signal.setitimer(signal.ITIMER_REAL, 20)

    # Add stacktrace to error message
    error = str(msg)
    error += "\n" + traceback.format_exc()

    GatewayMqttClient.instance().log_message('ERROR', f'FATAL ERROR: {msg}')
    print("FATAL ERROR:")
    print(msg)
    sleep(1)

    # Trigger the graceful shutdown handler
    signal.raise_signal( signal.SIGINT )
    sleep(20)
    sys.exit(1)