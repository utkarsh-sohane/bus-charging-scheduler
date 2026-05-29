from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.models import (
    Bus,
    Charger,
    Operator,
    OptimizationWeights,
    RouteStop,
    Scenario,
    ScenarioConfig,
)
from src.route_utils import DIRECTION_BK, parse_time_to_minutes


def _parse_weights(data: dict) -> OptimizationWeights:
    w = data.get("weights", data.get("optimization_weights", {}))
    return OptimizationWeights.from_dict(w)


def _parse_config(data: dict) -> ScenarioConfig:
    cfg = data.get("config", {})
    return ScenarioConfig(
        max_range_km=float(cfg.get("max_range_km", 240)),
        charge_duration_min=float(cfg.get("charge_duration_min", 25)),
        speed_kmph=float(cfg.get("speed_kmph", 60)),
        min_charges=int(cfg.get("min_charges", 2)),
    )


def _parse_bus(raw: dict) -> Bus:
    direction = raw.get("direction", DIRECTION_BK)
    if "departure_time" in raw:
        dep = parse_time_to_minutes(raw["departure_time"])
    else:
        dep = float(raw["departure_time_min"])
    return Bus(
        id=raw["id"],
        operator_id=raw["operator_id"],
        direction=direction,
        departure_time_min=dep,
    )


def load_scenario(path: Path | str) -> Scenario:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    route = [
        RouteStop(
            id=s["id"],
            name=s["name"],
            distance_km=float(s["distance_km"]),
            has_charging=bool(s.get("has_charging", True)),
        )
        for s in data["route"]
    ]

    chargers = [
        Charger(id=c["id"], station_id=c["station_id"])
        for c in data.get("chargers", [])
    ]

    operators = [
        Operator(id=o["id"], name=o["name"]) for o in data.get("operators", [])
    ]

    buses = [_parse_bus(b) for b in data.get("buses", [])]

    return Scenario(
        id=data.get("id", path.stem),
        name=data.get("name", path.stem),
        description=data.get("description", ""),
        route=route,
        chargers=chargers,
        operators=operators,
        buses=buses,
        weights=_parse_weights(data),
        config=_parse_config(data),
    )


def list_scenarios(directory: Path | str) -> list[Path]:
    directory = Path(directory)
    files: list[Path] = []
    for pattern in ("scenario_*.json", "scenario_*.yaml", "scenario_*.yml"):
        files.extend(sorted(directory.glob(pattern)))
    return files


def load_scenario_by_id(scenarios_dir: Path | str, scenario_id: str) -> Scenario:
    directory = Path(scenarios_dir)
    for path in list_scenarios(directory):
        scenario = load_scenario(path)
        if scenario.id == scenario_id:
            return scenario
    raise FileNotFoundError(f"No scenario with id '{scenario_id}' in {directory}")
