import os
import signal
from typing import Any

from modules.mqtt import GatewayMqttClient


def on_rpc_request(rpc_msg_id: str, method: Any, params: Any) -> None:
    """Handle incoming RPC requests"""
    print(f"RPC request: {rpc_msg_id} {method} ({params})")
    GatewayMqttClient.instance().publish_log(
        "INFO", f"RPC request: {method} ({params})")
    if method == "reboot":
        print("[RPC] Rebooting...")
        send_rpc_response(rpc_msg_id, "OK - Rebooting")
        os.system("reboot")
    elif method == "shutdown":
        print("[RPC] Shutting down...")
        send_rpc_response(rpc_msg_id, "OK - Shutting down")
        os.system("shutdown now")
    elif method == "exit":
        print("[RPC] Exiting...")
        send_rpc_response(rpc_msg_id, "OK - Exiting")
        signal.raise_signal(signal.SIGTERM)
    else:
        print(f"Unknown RPC method: {method}")
        GatewayMqttClient.instance().publish_log(
            "ERROR", f"Unknown RPC method: {method}")
        send_rpc_response(rpc_msg_id, "UNKNOWN_METHOD")


def send_rpc_response(rpc_msg_id: str, response: str) -> None:
    """Send an RPC response"""
    GatewayMqttClient.instance().publish_message_raw(
        "v1/devices/me/rpc/response/" + rpc_msg_id,
        "{\"message\": \"" + response + "\"}")
