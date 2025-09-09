from typing import Any, Dict, Optional, Tuple


def safe_get(d: Dict[str, Any], key: str, default: Any = "N/A") -> Any:
    """Return a value safely (works with nested externalIds if needed)."""
    if not d:
        return default
    return d.get(key, default)


def parse_series_value_and_time(series: Any) -> Tuple[Optional[float], Optional[str]]:
    """Parse Samsara series to (value, time)."""
    if not series:
        return None, None

    try:
        if isinstance(series, dict):
            data = series.get("data")
            if isinstance(data, list) and data:
                last = data[-1]
                return last.get("value"), last.get("time") or last.get("timestamp")
            return series.get("value"), series.get("time") or series.get("timestamp")

        if isinstance(series, list) and series:
            last = series[-1]
            return last.get("value"), last.get("time") or last.get("timestamp")

        if isinstance(series, (int, float)):
            return float(series), None
    except Exception:
        return None, None

    return None, None


def meters_to_miles(meters: float) -> int:
    """Convert meters to rounded miles (int)."""
    return int(round(float(meters) / 1609.34))


def extract_odometer_miles(vehicle: Dict[str, Any]) -> Optional[int]:
    """Extract odometer in miles from vehicle payload."""
    dotted_key = vehicle.get("obdOdometerMeters.value")
    if isinstance(dotted_key, (int, float)):
        return meters_to_miles(dotted_key)

    series = vehicle.get("obdOdometerMeters")
    meters, _ = parse_series_value_and_time(series)
    if meters is not None:
        return meters_to_miles(meters)

    for alt_key in ("odometerMeters", "odometer", "lastOdometerMeters"):
        alt = vehicle.get(alt_key)
        if isinstance(alt, (int, float)):
            return meters_to_miles(float(alt))

    return None
