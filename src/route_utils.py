from __future__ import annotations

from src.models import RouteStop

DIRECTION_BK = "bengaluru_to_kochi"
DIRECTION_KB = "kochi_to_bengaluru"


def parse_time_to_minutes(value: str | int | float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if ":" in text:
        h, m = text.split(":", 1)
        return int(h) * 60 + int(m)
    return float(text)


def format_minutes(minutes: float) -> str:
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"


def travel_minutes(distance_km: float, speed_kmph: float) -> float:
    """At 60 km/h, 100 km takes 100 minutes (distance equals minutes)."""
    if distance_km <= 0:
        return 0.0
    return distance_km / speed_kmph * 60.0


def origin_index(direction: str) -> int:
    return 0 if direction == DIRECTION_BK else -1


def destination_index(direction: str, route_len: int) -> int:
    return route_len - 1 if direction == DIRECTION_BK else 0


def leg_distance_km(
    route: list[RouteStop], from_idx: int, to_idx: int
) -> float:
    return abs(route[to_idx].distance_km - route[from_idx].distance_km)


def charging_indices(route: list[RouteStop], direction: str) -> list[int]:
    indices = [i for i, s in enumerate(route) if s.has_charging]
    if direction == DIRECTION_KB:
        return list(reversed(indices))
    return indices
