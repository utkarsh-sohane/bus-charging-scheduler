from __future__ import annotations

from itertools import combinations

from src.models import Bus, RouteStop, Scenario
from src.route_utils import (
    DIRECTION_BK,
    destination_index,
    leg_distance_km,
    origin_index,
    charging_indices,
    travel_minutes,
)


def _waypoints(
    route: list[RouteStop],
    direction: str,
    charge_stops: list[int],
) -> list[int]:
    start = origin_index(direction)
    end = destination_index(direction, len(route))
    if direction == DIRECTION_BK:
        return [start, *charge_stops, end]
    return [start, *charge_stops, end]


def is_valid_plan(
    route: list[RouteStop],
    direction: str,
    charge_stops: tuple[int, ...],
    max_range_km: float,
    min_charges: int = 2,
) -> bool:
    if len(charge_stops) < min_charges:
        return False

    ordered = charging_indices(route, direction)
    stop_set = set(charge_stops)
    if not all(s in ordered for s in charge_stops):
        return False
    # Must follow route order
    positions = [ordered.index(s) for s in charge_stops]
    if positions != sorted(positions):
        return False

    points = _waypoints(route, direction, list(charge_stops))
    for a, b in zip(points, points[1:]):
        if leg_distance_km(route, a, b) > max_range_km + 1e-6:
            return False
    return True


def enumerate_valid_plans(
    route: list[RouteStop],
    direction: str,
    max_range_km: float,
    min_charges: int = 2,
) -> list[list[int]]:
    stations = charging_indices(route, direction)
    plans: list[list[int]] = []
    for r in range(min_charges, len(stations) + 1):
        for combo in combinations(stations, r):
            if is_valid_plan(route, direction, combo, max_range_km, min_charges):
                plans.append(list(combo))
    return plans


def estimate_arrival_times(
    route: list[RouteStop],
    direction: str,
    charge_stops: list[int],
    departure_min: float,
    speed_kmph: float,
) -> dict[int, float]:
    """Arrival time at each charging stop (ignoring queue wait)."""
    points = _waypoints(route, direction, charge_stops)
    times: dict[int, float] = {}
    t = departure_min
    for a, b in zip(points, points[1:]):
        t += travel_minutes(leg_distance_km(route, a, b), speed_kmph)
        if b in charge_stops:
            times[b] = t
    return times


def assign_charging_plans(scenario: Scenario) -> dict[str, list[int]]:
    """
    Choose a valid charging plan per bus before simulation.
    Minimizes projected station overlap with already-assigned buses.
    """
    route = scenario.route
    cfg = scenario.config
    min_charges = cfg.min_charges
    max_range = cfg.max_range_km

    # Track projected arrivals per station from assigned plans
    projected: dict[int, list[float]] = {i: [] for i, s in enumerate(route) if s.has_charging}

    assignments: dict[str, list[int]] = {}
    buses_sorted = sorted(scenario.buses, key=lambda b: b.departure_time_min)

    for bus in buses_sorted:
        candidates = enumerate_valid_plans(
            route, bus.direction, max_range, min_charges
        )
        if not candidates:
            raise ValueError(f"No valid charging plan for {bus.id} ({bus.direction})")

        best_plan = candidates[0]
        best_score = float("inf")

        for plan in candidates:
            arrivals = estimate_arrival_times(
                route, bus.direction, plan, bus.departure_time_min, cfg.speed_kmph
            )
            overlap = 0.0
            for idx, arr in arrivals.items():
                for other in projected.get(idx, []):
                    overlap += max(0.0, 30.0 - abs(arr - other))
            # Prefer fewer stops when overlap equal (less total delay risk)
            score = overlap + len(plan) * 0.01
            if score < best_score:
                best_score = score
                best_plan = plan

        assignments[bus.id] = best_plan
        arrivals = estimate_arrival_times(
            route, bus.direction, best_plan, bus.departure_time_min, cfg.speed_kmph
        )
        for idx, arr in arrivals.items():
            projected[idx].append(arr)

    return assignments
