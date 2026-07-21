import math

def avg_list(input_list: list[float], round_digits: int = 2) -> float:
    """Averages a list of float.
    Returns a float rounded to defined digits."""
    return round(sum(input_list) / len(input_list), round_digits)

def circular_mean_degrees(input_list: list[float], round_digits: int = 2) -> float:
    sin_sum = sum(math.sin(math.radians(value)) for value in input_list)
    cos_sum = sum(math.cos(math.radians(value)) for value in input_list)

    direction = math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0
    return round(direction, round_digits) % 360.0