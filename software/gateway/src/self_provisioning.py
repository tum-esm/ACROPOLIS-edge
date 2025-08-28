import json
import os
import socket
import ssl
from random import randrange
from time import sleep
import argparse

from paho.mqtt.client import Client

from modules.logging import debug

# global variable to contain the reply from the self-provisioning request
provision_reply = None


# Perform self-provisioning if needed to get an access-token for the gateway
def self_provisioning_get_access_token(args: argparse.Namespace) -> (bool, str):
    global provision_reply
    # check if access token exists
    access_token_path_env_var = os.environ.get("THINGSBOARD_ACCESS_TOKEN") or "./tb_access_token"

    if os.path.exists(access_token_path_env_var):
        with open(access_token_path_env_var, "r") as f:
            access_token = f.read()
            if access_token is not None and len(access_token) > 3:
                debug(f"Access token found in file {access_token_path_env_var}")
            return False, access_token

    # else, perform self-provisioning
    debug("No access token found, performing self-provisioning...")
    mqtt_client = Client()
    mqtt_client.username_pw_set("provision", None)
    mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    mqtt_client.on_connect = (lambda client, userdata, flags, rc: debug(f"Connected to ThingsBoard for self-provisioning with result code {rc}"))
    mqtt_client.connect(args.tb_host, args.tb_port)

    # set up the callback to receive the reply from the self-provisioning request
    def on_message_callback(client, userdata, message):
        global provision_reply
        provision_reply = message.payload
    mqtt_client.on_message = on_message_callback
    mqtt_client.subscribe("/provision/response", qos=1)

    mqtt_client.loop_start()
    sleep(0.1)

    mqtt_client.publish("/provision/request",
                        payload=json.dumps({
                            "deviceName": get_device_name(args),
                            "provisionDeviceKey": os.environ.get("THINGSBOARD_PROVISION_DEVICE_KEY") or "u89nftek43npopnvnt21",
                            "provisionDeviceSecret": os.environ.get("THINGSBOARD_PROVISION_DEVICE_SECRET") or "r4acqug0fzh2wii4o4n6"
                        }), qos=1 )

    for _ in range(100):
        if provision_reply is not None:
            break
        sleep(0.1)
    mqtt_client.loop_stop()
    mqtt_client.disconnect()

    if provision_reply is not None:
        # parse string to json
        provision_reply = json.loads(provision_reply)

        # check for error
        status = provision_reply.get("status")
        if status is not None and status == "FAILURE":
            debug(f"Self-provisioning failed with error: {provision_reply.get("errorMsg")}")
            exit(1)

        credentials_type = provision_reply.get("credentialsType")
        if credentials_type is not None and credentials_type == "ACCESS_TOKEN":
            credentials_value = provision_reply.get("credentialsValue")
            if credentials_value is not None:
                debug("Self-provisioning successful.")
                debug(f"Writing access token to file: {access_token_path_env_var}")
                with open(access_token_path_env_var, "w") as f:
                    f.write(credentials_value)
                return True, credentials_value

    debug("Self-provisioning failed")
    debug(f"Reply: {provision_reply}")
    exit(1)


def get_device_name(args: argparse.Namespace) -> str:
    return (
            getattr(args, "device_name", None)
        or os.environ.get("THINGSBOARD_DEVICE_NAME")
        or socket.gethostname()
        or ("teg-" + str(randrange(1000000, 9999999, 1)))
    )