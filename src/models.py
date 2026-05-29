from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MAX_RANGE_KM = 240.0
CHARGE_DURATION_MIN = 25.0
MIN_CHARGES = 2

DEFAULT_WEIGHTS: dict[str, float] = {
    "individual": 1.0,
    "operator": 1.0,
    "overall": 1.0,
}


@dataclass(frozen=True)
class RouteStop:
    id: str
    name: str
    distance_km: float
    has_charging: bool = True


@dataclass(frozen=True)
class Charger:
    id: str
    station_id: str


@dataclass(frozen=True)
class Operator:
    id: str
    name: str


@dataclass(frozen=True)
class Bus:
    id: str
    operator_id: str
    direction: str
    departure_time_min: float


@dataclass(frozen=True)
class OptimizationWeights:
    """Immutable weight map — add keys in scenario JSON without code changes."""

    values: dict[str, float]

    @classmethod
    def from_dict(cls, raw: dict[str, float] | None) -> OptimizationWeights:
        merged = dict(DEFAULT_WEIGHTS)
        if raw:
            merged.update({k: float(v) for k, v in raw.items()})
        return cls(values=merged)

    def get(self, key: str, default: float = 0.0) -> float:
        return self.values.get(key, default)

    @property
    def individual(self) -> float:
        return self.get("individual")

    @property
    def operator(self) -> float:
        return self.get("operator")

    @property
    def overall(self) -> float:
        return self.get("overall")


@dataclass
class ScenarioConfig:
    max_range_km: float = MAX_RANGE_KM
    charge_duration_min: float = CHARGE_DURATION_MIN
    speed_kmph: float = 60.0
    min_charges: int = MIN_CHARGES


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    route: list[RouteStop]
    chargers: list[Charger]
    operators: list[Operator]
    buses: list[Bus]
    weights: OptimizationWeights
    config: ScenarioConfig = field(default_factory=ScenarioConfig)


@dataclass
class ChargingVisit:
    station_id: str
    station_name: str
    arrival_time_min: float
    wait_time_min: float
    charge_start_min: float
    charge_end_min: float
    charger_id: str


@dataclass
class BusSchedule:
    bus_id: str
    operator_id: str
    operator_name: str
    direction: str
    departure_time_min: float
    arrival_time_min: float
    total_wait_min: float
    charging_plan: list[str] = field(default_factory=list)
    visits: list[ChargingVisit] = field(default_factory=list)


@dataclass
class ChargerTimelineEntry:
    bus_id: str
    start_min: float
    end_min: float


@dataclass
class StationSchedule:
    station_id: str
    station_name: str
    charge_order: list[str]
    queue_snapshots: list[dict[str, Any]] = field(default_factory=list)
    charger_timelines: dict[str, list[ChargerTimelineEntry]] = field(
        default_factory=dict
    )


@dataclass
class ScheduleResult:
    scenario_id: str
    scenario_name: str
    bus_schedules: list[BusSchedule]
    station_schedules: list[StationSchedule]
    weights: OptimizationWeights
    validation_errors: list[str] = field(default_factory=list)
