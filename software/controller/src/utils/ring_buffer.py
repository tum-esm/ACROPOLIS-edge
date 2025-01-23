from typing import Any, Optional


class RingBuffer:
    """Appends float values in a ring buffer and returns the average of it"""

    def __init__(self, size: int):
        assert size > 0
        self.size = size
        self.ring_buffer: list[Any] = []

    def append(self, value: Optional[float]) -> None:
        if value is not None:
            if len(self.ring_buffer) < self.size:
                self.ring_buffer.append(value)
            if len(self.ring_buffer) == self.size:
                self.ring_buffer = self.ring_buffer[1:]
                self.ring_buffer.append(value)
                assert len(self.ring_buffer) == self.size

    def avg(self) -> Any:
        if len(self.ring_buffer) > 0:
            value = sum(self.ring_buffer) / len(self.ring_buffer)
            return round(value, 2)
        else:
            return None

    def median(self) -> Any:
        if len(self.ring_buffer) > 0:
            sorted_buffer = sorted(self.ring_buffer)
            mid = len(sorted_buffer) // 2
            if len(sorted_buffer) % 2 == 0:
                # Average of two middle values for even length
                return round((sorted_buffer[mid - 1] + sorted_buffer[mid]) / 2,
                             2)
            else:
                # Middle value for odd length
                return round(sorted_buffer[mid], 2)
        else:
            return None

    def calculate_calibration_median(self) -> Any:
        """Returns the median after cutting the first 30% and last 5% of the buffer"""
        n = len(self.ring_buffer)
        start_index = int(n * 0.3)  # First 30%
        end_index = int(n * 0.95)  # Last 5%

        # Slice the list
        trimmed_buffer = self.ring_buffer[start_index:end_index]

        sorted_buffer = sorted(trimmed_buffer)
        mid = len(sorted_buffer) // 2
        if len(sorted_buffer) % 2 == 0:
            # Average of two middle values for even length
            return round((sorted_buffer[mid - 1] + sorted_buffer[mid]) / 2, 2)
        else:
            # Middle value for odd length
            return round(sorted_buffer[mid], 2)

    def clear(self) -> None:
        self.ring_buffer = []
