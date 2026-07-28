from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gpiozero.pins import Factory


def get_gpio_pin_factory() -> Factory:
    """Create the local GPIO Zero pin factory.

    Raspberry Pi OS Trixie uses the ``lgpio`` backend to access GPIO pins
    directly. No ``pigpiod`` daemon is required.
    """

    try:
        from gpiozero.pins.lgpio import LGPIOFactory
    except ImportError as error:
        raise ConnectionError(
            "The lgpio backend is unavailable. Install the 'python3-lgpio' package."
        ) from error

    try:
        return LGPIOFactory()
    except Exception as error:
        raise ConnectionError(
            "Failed to initialize the local GPIO backend."
        ) from error