from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from src.models import (
    BusSchedule,
    ChargerTimelineEntry,
    ChargingVisit,
    Scenario,
    ScheduleResult,
    StationSchedule,
)
from src.plans import assign_charging_plans
from src.route_utils import (
    destination_index,
    leg_distance_km,
    origin_index,
    travel_minutes,
)
from src.scoring.base import ScoringContext
from src.scoring.engine import ScoringEngine
from src.validation import validate_schedule


@dataclass(order=True)
class _Event:
    time: float
    seq: int
    kind: str = field(compare=False)
    bus_id: str = field(compare=False, default="")
    station_id: str = field(compare=False, default="")
    charger_id: str = field(compare=False, default="")


@dataclass
class _BusState:
    bus_id: str
    operator_id: str
    direction: str
    departure_time_min: float
    current_idx: int = 0
    current_time_min: float = 0.0
    total_wait_min: float = 0.0
    charge_plan: list[int] = field(default_factory=list)
    plan_pointer: int = 0
    visits: list[ChargingVisit] = field(default_factory=list)
    waiting_at: str | None = None
    wait_started: float = 0.0
    pending_arrival: float = 0.0
    finished: bool = False


@dataclass
class _ChargerState:
    charger_id: str
    station_id: str
    busy_until: float = 0.0
    timeline: list[ChargerTimelineEntry] = field(default_factory=list)


class Scheduler:
    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.scoring = ScoringEngine(scenario.weights)
        self._operators = {o.id: o for o in scenario.operators}
        self._chargers_by_station: dict[str, list[_ChargerState]] = {}
        for ch in scenario.chargers:
            self._chargers_by_station.setdefault(ch.station_id, []).append(
                _ChargerState(charger_id=ch.id, station_id=ch.station_id)
            )
        self._plans = assign_charging_plans(scenario)

    def run(self) -> ScheduleResult:
        scenario = self.scenario
        route = scenario.route
        cfg = scenario.config

        bus_states: dict[str, _BusState] = {}
        for bus in scenario.buses:
            start_idx = origin_index(bus.direction)
            bus_states[bus.id] = _BusState(
                bus_id=bus.id,
                operator_id=bus.operator_id,
                direction=bus.direction,
                departure_time_min=bus.departure_time_min,
                current_idx=start_idx,
                current_time_min=bus.departure_time_min,
                charge_plan=self._plans[bus.id],
            )

        schedulable_stations = {
            s.id for s in route if s.has_charging
        }
        station_queues: dict[str, list[str]] = {sid: [] for sid in schedulable_stations}
        station_charge_order: dict[str, list[str]] = {
            sid: [] for sid in schedulable_stations
        }

        seq = 0
        events: list[_Event] = []
        for bus in scenario.buses:
            heapq.heappush(
                events, _Event(bus.departure_time_min, seq, "depart", bus.id)
            )
            seq += 1

        def operator_charge_counts() -> dict[str, int]:
            counts: dict[str, int] = {o.id: 0 for o in scenario.operators}
            for st in bus_states.values():
                counts[st.operator_id] = counts.get(st.operator_id, 0) + len(
                    st.visits
                )
            return counts

        def operator_wait_totals() -> dict[str, float]:
            totals: dict[str, float] = {o.id: 0.0 for o in scenario.operators}
            for st in bus_states.values():
                totals[st.operator_id] += st.total_wait_min
            return totals

        def operator_bus_counts() -> dict[str, int]:
            counts: dict[str, int] = {}
            for b in scenario.buses:
                counts[b.operator_id] = counts.get(b.operator_id, 0) + 1
            return counts

        def network_wait(now: float) -> float:
            total = sum(st.total_wait_min for st in bus_states.values())
            for st in bus_states.values():
                if st.waiting_at:
                    total += now - st.wait_started
            return total

        def pending_wait_count() -> int:
            return sum(len(q) for q in station_queues.values())

        def start_charging(
            bus_id: str, station_id: str, charger: _ChargerState, now: float
        ) -> None:
            st = bus_states[bus_id]
            arrival = st.pending_arrival if st.pending_arrival else now
            wait = max(0.0, now - arrival)
            st.total_wait_min += wait
            st.waiting_at = None
            st.pending_arrival = 0.0

            charge_start = now
            charge_end = now + cfg.charge_duration_min
            charger.busy_until = charge_end
            charger.timeline.append(
                ChargerTimelineEntry(bus_id, charge_start, charge_end)
            )
            station_charge_order[station_id].append(bus_id)

            st.visits.append(
                ChargingVisit(
                    station_id=station_id,
                    station_name=next(s.name for s in route if s.id == station_id),
                    arrival_time_min=arrival,
                    wait_time_min=wait,
                    charge_start_min=charge_start,
                    charge_end_min=charge_end,
                    charger_id=charger.charger_id,
                )
            )
            st.current_time_min = charge_end

            nonlocal seq
            heapq.heappush(
                events,
                _Event(
                    charge_end,
                    seq,
                    "charge_done",
                    bus_id,
                    station_id,
                    charger.charger_id,
                ),
            )
            seq += 1

        def try_assign_charger(station_id: str, now: float) -> None:
            queue = station_queues.get(station_id, [])
            while queue:
                chargers = self._chargers_by_station.get(station_id, [])
                free = [c for c in chargers if c.busy_until <= now + 1e-9]
                if not free:
                    break

                op_waits = operator_wait_totals()
                op_counts = operator_bus_counts()
                op_charges = operator_charge_counts()
                net_wait = network_wait(now)
                pending = pending_wait_count()

                contexts: list[ScoringContext] = []
                for bid in list(queue):
                    st = bus_states[bid]
                    wait = (
                        now - st.wait_started
                        if st.waiting_at == station_id
                        else 0.0
                    )
                    contexts.append(
                        ScoringContext(
                            bus_id=bid,
                            operator_id=st.operator_id,
                            wait_time_min=wait,
                            total_wait_min=st.total_wait_min,
                            operator_total_wait_min=op_waits.get(
                                st.operator_id, 0.0
                            ),
                            operator_bus_count=op_counts.get(st.operator_id, 1),
                            operator_charges_so_far=op_charges.get(
                                st.operator_id, 0
                            ),
                            network_total_wait_min=net_wait,
                            pending_wait_count=pending,
                        )
                    )

                winner = self.scoring.pick_winner(contexts)
                queue.remove(winner.bus_id)
                start_charging(winner.bus_id, station_id, free[0], now)

        def advance_bus(bus_id: str) -> None:
            nonlocal seq
            st = bus_states[bus_id]
            if st.finished:
                return

            dest = destination_index(st.direction, len(route))

            if st.plan_pointer < len(st.charge_plan):
                target_idx = st.charge_plan[st.plan_pointer]
                needs_charge = True
            elif st.current_idx != dest:
                target_idx = dest
                needs_charge = False
            else:
                st.finished = True
                return

            leg_km = leg_distance_km(route, st.current_idx, target_idx)
            travel = travel_minutes(leg_km, cfg.speed_kmph)
            arrival = st.current_time_min + travel
            st.current_idx = target_idx

            if needs_charge:
                station_id = route[target_idx].id
                st.plan_pointer += 1
                st.pending_arrival = arrival
                st.current_time_min = arrival

                chargers = self._chargers_by_station.get(station_id, [])
                free = [c for c in chargers if c.busy_until <= arrival + 1e-9]
                if free:
                    start_charging(bus_id, station_id, free[0], arrival)
                else:
                    st.waiting_at = station_id
                    st.wait_started = arrival
                    station_queues[station_id].append(bus_id)
                    heapq.heappush(
                        events, _Event(arrival, seq, "assign", "", station_id)
                    )
                    seq += 1
            else:
                st.current_time_min = arrival
                st.finished = True

        while events:
            ev = heapq.heappop(events)
            now = ev.time

            if ev.kind == "depart":
                advance_bus(ev.bus_id)

            elif ev.kind == "continue":
                advance_bus(ev.bus_id)

            elif ev.kind == "assign":
                try_assign_charger(ev.station_id, now)
                for sid in station_queues:
                    if sid != ev.station_id:
                        try_assign_charger(sid, now)

            elif ev.kind == "charge_done":
                try_assign_charger(ev.station_id, now)
                for sid in station_queues:
                    if sid != ev.station_id:
                        try_assign_charger(sid, now)
                heapq.heappush(events, _Event(now, seq, "continue", ev.bus_id))
                seq += 1

        bus_schedules: list[BusSchedule] = []
        for bus in scenario.buses:
            st = bus_states[bus.id]
            op = self._operators.get(st.operator_id)
            plan_names = [route[i].name for i in self._plans[bus.id]]
            bus_schedules.append(
                BusSchedule(
                    bus_id=bus.id,
                    operator_id=st.operator_id,
                    operator_name=op.name if op else st.operator_id,
                    direction=bus.direction,
                    departure_time_min=st.departure_time_min,
                    arrival_time_min=st.current_time_min,
                    total_wait_min=st.total_wait_min,
                    charging_plan=plan_names,
                    visits=st.visits,
                )
            )

        station_schedules: list[StationSchedule] = []
        for stop in route:
            if not stop.has_charging:
                continue
            timelines = {
                ch.charger_id: list(ch.timeline)
                for ch in self._chargers_by_station.get(stop.id, [])
            }
            station_schedules.append(
                StationSchedule(
                    station_id=stop.id,
                    station_name=stop.name,
                    charge_order=station_charge_order.get(stop.id, []),
                    charger_timelines=timelines,
                )
            )

        result = ScheduleResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            bus_schedules=bus_schedules,
            station_schedules=station_schedules,
            weights=scenario.weights,
        )
        result.validation_errors = validate_schedule(scenario, result)
        return result
