import time
import traceback
from datetime import datetime
from os.path import join
from typing import Literal, Optional
import os
import sys
import pytz

from custom_types import mqtt_playload_types, config_types
from utils import message_queue, shell_commands
from utils.paths import ACROPOLIS_CONTROLLER_LOGS_PATH


def _pad_str_right(text: str,
                   min_width: int,
                   fill_char: Literal["0", " "] = " ") -> str:
    if len(text) >= min_width:
        return text
    else:
        return text + (fill_char * (min_width - len(text)))


class Logger:

    def __init__(self,
                 config: config_types.Config,
                 origin: str = "insert-name-here") -> None:

        self.config = config
        self.origin: str = origin
        self.print_to_console = self.config.active_components.log_to_console
        self.write_to_file = self.config.active_components.log_to_file
        self.message_queue = message_queue.MessageQueue()

    def horizontal_line(self,
                        fill_char: Literal["-", "=", ".", "_"] = "=") -> None:
        """Writes a debug log line, used for verbose output"""
        self._write_log_line("INFO", fill_char * 46)

    def debug(self, message: str) -> None:
        """Writes a debug log line, used for verbose output"""
        self._write_log_line("DEBUG", message)

    def info(
        self,
        message: str,
        forward: bool = False,
        details: str = "",
    ) -> None:
        """Writes an info log line. Forwards to MQTT client when set to True."""
        if len(details) == 0:
            self._write_log_line("INFO", message)
        else:
            self._write_log_line("INFO", f"{message}, details: {details}")
        if forward:
            self._enqueue_message(
                level="INFO",
                subject=message,
                details=details,
            )

    def warning(
        self,
        message: str,
        forward: bool = False,
        details: str = "",
    ) -> None:
        """Writes a warning log line, sends the message via MQTT when set to True."""
        if len(details) == 0:
            self._write_log_line("WARNING", message)
        else:
            self._write_log_line("WARNING", f"{message}, details: {details}")
        if forward:
            self._enqueue_message(
                level="WARNING",
                subject=message,
            )

    def error(
        self,
        message: str,
        forward: bool = False,
        details: str = "",
    ) -> None:
        """Writes an error log line, sends the message via MQTT when set to True."""
        if len(details) == 0:
            self._write_log_line("ERROR", message)
        else:
            self._write_log_line(
                "ERROR",
                "\n".join([
                    message,
                    "--- details: -----------------",
                    details,
                    "------------------------------",
                ]),
            )
        if forward:
            self._enqueue_message(level="ERROR",
                                  subject=message,
                                  details=details)

    def exception(
        self,
        e: Exception,
        label: Optional[str] = None,
        forward: bool = False,
    ) -> None:
        """Logs the traceback of an exception, sends the message via MQTT when set to True."""
        exception_name = traceback.format_exception_only(type(e), e)[0].strip()
        exception_traceback = "\n".join(
            traceback.format_exception(type(e), e, e.__traceback__)).strip()
        exception_details = "None"
        if isinstance(e,
                      shell_commands.CommandLineException) and (e.details
                                                                is not None):
            exception_details = e.details.strip()

        subject_string = (exception_name
                          if label is None else f"{label}, {exception_name}")
        details_string = (f"--- details: -----------------\n" +
                          f"{exception_details}\n" +
                          f"--- traceback: ---------------\n" +
                          f"{exception_traceback}\n" +
                          f"------------------------------")

        self._write_log_line("EXCEPTION",
                             f"{subject_string}\n{details_string}")
        if forward:
            self._enqueue_message(
                level="ERROR",
                subject=subject_string,
                details=details_string,
            )

    def _write_log_line(self, level: str, message: str) -> None:
        """Formats the log line string and writes it to the appropriate log file."""
        # Get the current local time as a timezone-aware datetime object
        now_local = datetime.now().astimezone(
            pytz.timezone(self.config.local_time_zone))

        # Format the timestamp to include milliseconds
        timestamp = now_local.strftime(
            '%Y-%m-%d %H:%M:%S.%f')[:-3]  # Trim microseconds to milliseconds

        offset_str = self.determine_UTC_offset(now_local=now_local)

        # Construct the log string with proper formatting
        log_string = (f"{timestamp} {offset_str} "
                      f"- {_pad_str_right(self.origin, min_width=23)} "
                      f"- {_pad_str_right(level, min_width=13)} "
                      f"- {message}\n")

        # Print to console if enabled
        if self.print_to_console:
            print(log_string, end="")
            sys.stdout.flush()

        # Write to file if enabled
        if self.write_to_file:
            # YYYY-MM-DD.log
            log_file_name = now_local.strftime('%Y-%m-%d') + ".log"
            log_file_path = join(ACROPOLIS_CONTROLLER_LOGS_PATH, log_file_name)

            # Ensure the log directory exists
            os.makedirs(ACROPOLIS_CONTROLLER_LOGS_PATH, exist_ok=True)

            # Append the log string to the file
            with open(log_file_path, "a") as f1:
                f1.write(log_string)

    def determine_UTC_offset(self, now_local: datetime) -> str:

        # Calculate UTC offset in hours, rounded to one decimal place
        utc_offset_td = now_local.utcoffset()
        if utc_offset_td is not None:
            utc_offset = round(utc_offset_td.total_seconds() / 3600, 1)
        else:
            # Fallback if utcoffset() returns None
            utc_offset = 0.0

        # If UTC offset is an integer, display without decimal
        if utc_offset == int(utc_offset):
            utc_offset = int(utc_offset)

        # Format UTC offset string
        if utc_offset < 0:
            return f"UTC{utc_offset}"
        else:
            return f"UTC+{utc_offset}"

    def _enqueue_message(
        self,
        level: Literal["INFO", "WARNING", "ERROR"],
        subject: str,
        details: str = "",
    ) -> None:
        subject = f"{self.origin} - {subject}"

        if len(subject) > 256:
            extension_message_subject = f" ... CUT ({len(subject)} -> 256)"
            subject = (subject[:(256 - len(extension_message_subject))] +
                       extension_message_subject)

        if len(details) > 16384:
            extension_message_details = f" ... CUT ({len(details)} -> 16384)"
            details = (details[:(16384 - len(extension_message_details))] +
                       extension_message_details)

        assert (len(subject) <= 256)
        assert (len(details) <= 16384)

        time.sleep(1)  # Ensure that log message has a unique timestamp

        self.message_queue.enqueue_message(
            timestamp=int(time.time()),
            payload=mqtt_playload_types.MQTTLogMessage(
                severity=level,
                message=subject + " " + details,
            ),
        )
