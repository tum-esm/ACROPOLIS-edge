import json
import os
import queue
import signal
import subprocess
import threading
from time import sleep, monotonic
from typing import Any, Optional

import utils.paths
from modules import sqlite
from modules.docker_client import GatewayDockerClient
from modules.file_writer import GatewayFileWriter
from modules.mqtt import GatewayMqttClient

from modules.logging import info, error, debug
from on_mqtt_msg.check_for_file_hashes_update import FILE_HASHES_TB_KEY


def rpc_reboot(rpc_msg_id: str, _method: Any, _params: Any):
    """Reboot the device"""
    info("[RPC] Rebooting...")
    send_rpc_response(rpc_msg_id, "OK - Rebooting")
    sleep(3)
    os.system("reboot")
    sleep(3)

def rpc_shutdown(rpc_msg_id: str, _method: Any, _params: Any):
    info("[RPC] Shutting down...")
    send_rpc_response(rpc_msg_id, "OK - Shutting down")
    sleep(3)
    os.system("shutdown now")

def rpc_exit(rpc_msg_id: str, _method: Any, _params: Any):
    info("[RPC] Exiting...")
    send_rpc_response(rpc_msg_id, "OK - Exiting")
    sleep(3)
    signal.raise_signal(signal.SIGTERM)

def rpc_restart_controller(rpc_msg_id: str, _method: Any, _params: Any):
    info("[RPC] Restarting controller...")
    send_rpc_response(rpc_msg_id, "OK - Restarting Controller")
    sleep(3)
    GatewayDockerClient().stop_controller()

def rpc_ping(rpc_msg_id: str, _method: Any, _params: Any):
    info("[RPC] Pong")
    send_rpc_response(rpc_msg_id, "Pong")


def rpc_init_files(rpc_msg_id: str, _method: Any, _params: Any):
    info("[RPC] Init files")

    # setup file hashes client attribute
    GatewayMqttClient().publish_message_raw("v1/devices/me/attributes", json.dumps({
        FILE_HASHES_TB_KEY: {}
    }))
    GatewayFileWriter().set_tb_hashes({})

    # request file definitions again to verify everything is correct
    GatewayMqttClient().request_attributes({"sharedKeys": f"FILES"})
    send_rpc_response(rpc_msg_id, "Files client attributes initialized")

def rpc_run_command(rpc_msg_id: str, _method: Any, params: Any):
    # Read command parameters
    if type(params) is not dict:
        return send_rpc_method_error(rpc_msg_id, "Running command failed: params is not a dictionary")
    if "command" not in params:
        return send_rpc_method_error(rpc_msg_id, "Running command failed: missing 'command' in params")
    if type(params["command"]) is not list or any(type(cmd) is not str for cmd in params["command"]):
        return send_rpc_method_error(rpc_msg_id, "Running command failed: 'command' must be a list of strings")
    if "timeout_s" in params and type(params["timeout_s"]) is not int:
        return send_rpc_method_error(rpc_msg_id, "Running command failed: 'timeout_s' must be an integer")
    timeout_s = params["timeout_s"] if "timeout_s" in params else 30
    command = params["command"]

    info(f"[RPC] Running command: ['{command}']")
    def read_stream_to_queue(stream, out_q: queue.Queue[str]) -> None:
        """Continuously read lines from `stream` and put them on a queue."""
        with stream:  # closes the pipe on exit
            for line in iter(stream.readline, ''):   # '' ⇒ EOF in text mode
                out_q.put(line)
    def read_lines_from_queue(line_queue: queue.Queue[str]) -> list[str]:
        collected_lines = []
        while True:
             try:
                 line = line_queue.get_nowait()
             except queue.Empty:
                 break
             collected_lines.append(line)
        return collected_lines

    # Run the command
    start_timestamp = monotonic()
    sub_process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr → stdout
        text=True,  # get str, not bytes
        bufsize=1,  # line‑buffered
        encoding='utf‑8', # decode stdout to string via utf-8
        errors='replace' # replace invalid characters with placeholder char during utf-8 decoding
    )

    stdout_line_queue: queue.Queue[str] = queue.Queue()
    pipe_reading_thread = threading.Thread(target=read_stream_to_queue, args=(sub_process.stdout, stdout_line_queue),
                                           daemon=True)
    pipe_reading_thread.start()

    output_lines: list[str] = []
    try:
        while sub_process.poll() is None:
            # Drain any lines that are already waiting
            output_lines.extend(read_lines_from_queue(stdout_line_queue))

            if monotonic() - start_timestamp >= timeout_s:
                sub_process.kill()
                sub_process.wait()  # ensure process has ended
                result = f"Error running command '{command}': Timeout after {timeout_s} seconds. Output: {'\n'.join(output_lines)}"
                return send_rpc_method_error(rpc_msg_id, result)

            sleep(0.05)  # small sleep: reduce CPU without blocking
        sub_process.wait()
    finally:
        # If we exit early (timeout or exception) make sure the reader thread ends
        pipe_reading_thread.join(timeout=1)

    # read any remaining lines from the queue
    while not stdout_line_queue.empty():
        output_lines.extend(read_lines_from_queue(stdout_line_queue))

    result = f"Command '{command}' exited with code {sub_process.returncode}. Output: {''.join(output_lines)}"
    send_rpc_response(rpc_msg_id, f"OK - Command executed - {result}")
    return None


def verify_start_end_timestamp_params(params: Any) -> Optional[str]:
    if type(params) is not dict:
        return "params is not a dictionary"
    if "start_timestamp_ms" not in params or "end_timestamp_ms" not in params:
        return "missing 'start_timestamp_ms' or 'end_timestamp_ms' in params"
    if type(params["start_timestamp_ms"]) is not int or type(params["end_timestamp_ms"]) is not int:
        return "'start_timestamp_ms' and 'end_timestamp_ms' must be integers"
    start_timestamp_ms = params["start_timestamp_ms"]
    end_timestamp_ms = params["end_timestamp_ms"]
    if start_timestamp_ms >= end_timestamp_ms:
        return "'start_timestamp_ms' must be less than 'end_timestamp_ms'"
    return None


def rpc_archive_republish_messages(rpc_msg_id: str, _method: Any, params: Any):
    params_verify_err = verify_start_end_timestamp_params(params)
    if params_verify_err is not None:
        return send_rpc_method_error(rpc_msg_id, f"Republishing archived messages failed: {params_verify_err}")

    start_timestamp_ms = params["start_timestamp_ms"]
    end_timestamp_ms = params["end_timestamp_ms"]
    if start_timestamp_ms <= 1735719469_000 or end_timestamp_ms >= 2524637869_000:
        return send_rpc_method_error(rpc_msg_id, "Republishing archived messages failed: 'start_timestamp_ms' and 'end_timestamp_ms' must be within the range of 1735719469_000 and 2524637869_000")

    archive_sqlite_db = sqlite.SqliteConnection(utils.paths.GATEWAY_ARCHIVE_DB_PATH)
    if archive_sqlite_db.db_unavailable:
        return send_rpc_method_error(rpc_msg_id, "Republishing archived messages failed: archive database unavailable")

    info(f"[RPC] Republishing messages - {start_timestamp_ms} -> {end_timestamp_ms}")
    message_count = 0
    while start_timestamp_ms < end_timestamp_ms:
        messages = archive_sqlite_db.execute("""SELECT id, timestamp_ms, message 
            FROM controller_archive 
            WHERE timestamp_ms > ? AND timestamp_ms < ? 
            ORDER BY timestamp_ms ASC LIMIT 200""",
            (start_timestamp_ms, end_timestamp_ms)
        )
        for message in messages:
            message_count += 1
            debug(f"Republishing message with timestamp {message[1]}")
            GatewayMqttClient().publish_telemetry(json.dumps({"ts": message[1], "values": json.loads(message[2])}))
            start_timestamp_ms = message[1]
        if len(messages) < 200:
            break
    archive_sqlite_db.close()
    send_rpc_response(rpc_msg_id, f"OK - {message_count} messages republished - {start_timestamp_ms} -> {end_timestamp_ms}")
    return None


def rpc_archive_discard_messages(rpc_msg_id: str, _method: Any, params: Any):
    params_verify_err = verify_start_end_timestamp_params(params)
    if params_verify_err is not None:
        return send_rpc_method_error(rpc_msg_id, f"Discarding archived messages failed: {params_verify_err}")

    start_timestamp_ms = params["start_timestamp_ms"]
    end_timestamp_ms = params["end_timestamp_ms"]
    if end_timestamp_ms >= 2524637869_000:
        return send_rpc_method_error(rpc_msg_id, "Discarding archived messages failed: 'end_timestamp_ms' must be < 2524637869_000")

    archive_sqlite_db = sqlite.SqliteConnection(utils.paths.GATEWAY_ARCHIVE_DB_PATH)
    if archive_sqlite_db.db_unavailable:
        return send_rpc_method_error(rpc_msg_id, "Discarding archived messages failed: archive database unavailable")

    info(f"[RPC] Discarding archived messages - {start_timestamp_ms} -> {end_timestamp_ms}")
    message_count = archive_sqlite_db.execute("DELETE FROM controller_archive WHERE timestamp_ms > ? AND timestamp_ms < ?",
                                              (start_timestamp_ms, end_timestamp_ms))
    archive_sqlite_db.close()
    send_rpc_response(rpc_msg_id, f"OK - {message_count} messages discarded - {start_timestamp_ms} -> {end_timestamp_ms}")
    return None


RPC_METHODS = {
    "reboot": {
        "description": "Reboot the device",
        "exec": rpc_reboot
    },
    "shutdown": {
        "description": "Shutdown the device",
        "exec": rpc_shutdown
    },
    "exit": {
        "description": "Exits the gateway process (triggers gateway restart)",
        "exec": rpc_exit
    },
    "ping": {
        "description": "Ping the device (returns 'pong' reply)",
        "exec": rpc_ping
    },
    "init_files": {
        "description": "Initialize file-related client attributes (FILE_HASHES, FILE_READ_*)",
        "exec": rpc_init_files
    },
    "restart_controller": {
        "description": "Restart the controller docker container",
        "exec": rpc_restart_controller
    },
    "run_command": {
        "description": "Run arbitrary command ({command: list [str], timeout_s: int [default 30s]}) - use with caution!",
        "exec": rpc_run_command
    },
    "archive_republish_messages": {
        "description": "Republish messages from archive ({start_timestamp_ms: int, end_timestamp_ms: int})",
        "exec": rpc_archive_republish_messages
    },
    "archive_discard_messages": {
        "description": "Discard messages from archive ({start_timestamp_ms: int, end_timestamp_ms: int})",
        "exec": rpc_archive_discard_messages
    },
}


def on_rpc_request(rpc_msg_id: str, method: str, params: Any) -> None:
    """Handle incoming RPC requests"""
    info(f"RPC request: {rpc_msg_id} {method} ({params})")
    if method in RPC_METHODS:
        try:
            RPC_METHODS[method]["exec"](rpc_msg_id, method, params) # type: ignore[operator]
        except Exception as e:
            error(f"Error executing RPC method '{method}': {e}")
            GatewayMqttClient().publish_log("ERROR", f"Error executing RPC method '{method}': {e}")
            send_rpc_response(rpc_msg_id, f"Error executing RPC method '{method}': {e}")
    elif method == "list":
        help_text = ["Available RPC methods:"]
        for method_name, method_data in RPC_METHODS.items():
            help_text.append(f"{method_name}: {method_data['description']}")
        send_rpc_response(rpc_msg_id, help_text)
    else:
        error(f"Unknown RPC method: {method}")
        GatewayMqttClient().publish_log("ERROR", f"Unknown RPC method: {method}")
        send_rpc_response(rpc_msg_id, f"Unknown RPC method: '{method}' - use command 'list' to get a list of available methods")


def send_rpc_response(rpc_msg_id: str, response: Any) -> bool:
    """Send an RPC response"""
    return GatewayMqttClient().publish_message_raw(
        "v1/devices/me/rpc/response/" + rpc_msg_id,
        json.dumps({"message": response})
    )

def send_rpc_method_error(rpc_msg_id, msg):
    error(f"[RPC] {msg}")
    send_rpc_response(rpc_msg_id, f"Error - {msg}")