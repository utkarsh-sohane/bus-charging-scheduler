from __future__ import annotations

from src.models import BusSchedule, ScheduleResult, Scenario
from src.route_utils import (
    destination_index,
    leg_distance_km,
    origin_index,
    travel_minutes,
)


def validate_schedule(scenario: Scenario, result: ScheduleResult) -> list[str]:
    errors: list[str] = []
    max_range = scenario.config.max_range_km
    charge_dur = scenario.config.charge_duration_min
    min_charges = scenario.config.min_charges
    route = scenario.route
    stop_by_id = {s.id: s for s in route}

    bus_by_id = {b.id: b for b in scenario.buses}
    charger_busy: dict[str, list[tuple[float, float, str]]] = {
        c.id: [] for c in scenario.chargers
    }

    for bus in result.bus_schedules:
        raw = bus_by_id.get(bus.bus_id)
        if raw is None:
            errors.append(f"Unknown bus {bus.bus_id}")
            continue

        direction = raw.direction
        start_idx = origin_index(direction)
        dest_idx = destination_index(direction, len(route))
        last_idx = start_idx
        last_time = bus.departure_time_min

        if len(bus.visits) < min_charges:
            errors.append(
                f"{bus.bus_id}: only {len(bus.visits)} charges "
                f"(minimum {min_charges})"
            )

        for visit in bus.visits:
            if visit.station_id not in stop_by_id:
                errors.append(f"{bus.bus_id}: unknown station {visit.station_id}")
                continue

            station = stop_by_id[visit.station_id]
            if not station.has_charging:
                errors.append(
                    f"{bus.bus_id}: charged at non-schedulable {visit.station_id}"
                )

            station_idx = next(
                i for i, s in enumerate(route) if s.id == visit.station_id
            )
            leg_km = leg_distance_km(route, last_idx, station_idx)
            if leg_km > max_range + 0.01:
                errors.append(
                    f"{bus.bus_id}: range violation {leg_km:.1f} km "
                    f"to {visit.station_id} (max {max_range} km)"
                )

            travel_min = travel_minutes(leg_km, scenario.config.speed_kmph)
            expected_arrival = last_time + travel_min
            if abs(visit.arrival_time_min - expected_arrival) > 0.5:
                errors.append(
                    f"{bus.bus_id}: arrival mismatch at {visit.station_id}"
                )

            if visit.wait_time_min < -0.01:
                errors.append(f"{bus.bus_id}: negative wait at {visit.station_id}")

            charge_len = visit.charge_end_min - visit.charge_start_min
            if abs(charge_len - charge_dur) > 0.01:
                errors.append(
                    f"{bus.bus_id}: charge duration {charge_len:.1f} min "
                    f"at {visit.station_id} (expected {charge_dur})"
                )

            timeline = charger_busy.setdefault(visit.charger_id, [])
            for start, end, other in timeline:
                if not (visit.charge_end_min <= start or visit.charge_start_min >= end):
                    errors.append(
                        f"Charger conflict on {visit.charger_id}: "
                        f"{bus.bus_id} vs {other}"
                    )
            timeline.append(
                (visit.charge_start_min, visit.charge_end_min, bus.bus_id)
            )

            last_idx = station_idx
            last_time = visit.charge_end_min

        final_leg = leg_distance_km(route, last_idx, dest_idx)
        if final_leg > max_range + 0.01:
            errors.append(
                f"{bus.bus_id}: cannot reach destination "
                f"({final_leg:.1f} km final leg)"
            )

    return errors
