import re

SEAT_RE = re.compile(r"^([A-Z])(\d+)$")
RANGE_RE = re.compile(r"^([A-Z])(\d+)-(\d+)$")


def seat_in_pattern(seat: str, seats_pattern: str) -> bool:
    """Check that ``seat`` (e.g. "A15") exists in a pattern like "A1-1000,B1-2000"."""
    match = SEAT_RE.match(seat)
    if not match:
        return False
    section, number = match.group(1), int(match.group(2))
    for part in seats_pattern.split(","):
        range_match = RANGE_RE.match(part.strip())
        if range_match and range_match.group(1) == section:
            start, end = int(range_match.group(2)), int(range_match.group(3))
            if start <= number <= end:
                return True
    return False
