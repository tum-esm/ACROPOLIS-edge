import pytest

from hardware.sensors import vaisala_wxt532
from hardware.sensors.vaisala_wxt532 import (MEASUREMENT_PATTERN,
                                             SerialInterface, VaisalaWXT532)

import re

# the Linux tty read buffer: the most one `serial.Serial.read_all()` returns
TTY_READ_BUFFER_BYTES = 4095

WIND_MESSAGE = "0R1,Dn=236D,Dm=283D,Dx=031D,Sn=0.0M,Sm=1.0M,Sx=2.2M\r\n"
STATUS_MESSAGE = "0R5,Th=25.9C,Vh=12.0N,Vs=15.2V,Vr=3.475V,Id=tumesmmw1\r\n"


class FakeSerial:
    """Hands out waiting bytes in chunks of at most the tty read buffer."""

    def __init__(self, waiting: bytes, refill: bytes = b"") -> None:
        self.waiting = waiting
        self.refill = refill  # arrives again after every read (never empty)
        self.reads = 0

    def reset_input_buffer(self) -> None:
        self.waiting = b""

    def read_all(self) -> bytes:
        self.reads += 1
        chunk = self.waiting[:TTY_READ_BUFFER_BYTES]
        self.waiting = self.waiting[TTY_READ_BUFFER_BYTES:] + self.refill
        return chunk


def interface_with(fake_serial: FakeSerial) -> SerialInterface:
    interface = SerialInterface.__new__(SerialInterface)
    interface.serial_interface = fake_serial
    interface.encoding = "cp1252"
    return interface


def one_cycle_of_messages(seconds: int = 130) -> str:
    """A wind message every second and a status message every third."""
    return "".join(WIND_MESSAGE + (STATUS_MESSAGE if second % 3 == 0 else "")
                   for second in range(seconds))


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vaisala_wxt532, "DRAIN_PAUSE_SECONDS", 0.0)


@pytest.mark.github_action
def test_read_all_returns_every_message_of_a_cycle() -> None:
    sent = one_cycle_of_messages()
    assert len(sent) > 2 * TTY_READ_BUFFER_BYTES  # more than one read holds

    received = interface_with(FakeSerial(sent.encode("cp1252"))).read_all()

    assert received == sent
    assert len(re.findall(MEASUREMENT_PATTERN, received)) == 130


@pytest.mark.github_action
def test_read_all_on_an_empty_port_returns_an_empty_string() -> None:
    fake_serial = FakeSerial(b"")
    assert interface_with(fake_serial).read_all() == ""
    assert fake_serial.reads == 1


@pytest.mark.github_action
def test_read_all_stops_when_the_port_never_runs_empty(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vaisala_wxt532, "DRAIN_TIMEOUT_SECONDS", 0.05)
    fake_serial = FakeSerial(b"x" * TTY_READ_BUFFER_BYTES,
                             refill=b"x" * TTY_READ_BUFFER_BYTES)
    received = interface_with(fake_serial).read_all()
    assert len(received) == fake_serial.reads * TTY_READ_BUFFER_BYTES


@pytest.mark.github_action
def test_discard_backlog_drops_unread_and_half_parsed_messages(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vaisala_wxt532.time, "sleep", lambda seconds: None)
    fake_serial = FakeSerial(one_cycle_of_messages().encode("cp1252"))
    sensor = VaisalaWXT532.__new__(VaisalaWXT532)
    sensor.simulate = False
    sensor.serial_interface = interface_with(fake_serial)
    sensor.current_input_stream = "0R1,Dn=2"
    sensor.buffered_messages = [WIND_MESSAGE.strip()]

    sensor.discard_backlog()

    assert fake_serial.waiting == b""
    assert sensor.current_input_stream == ""
    assert sensor.buffered_messages == []
    assert sensor.serial_interface.read_all() == ""
