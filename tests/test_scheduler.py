"""Smoke and assignment-spec tests for the charging scheduler."""

from pathlib import Path

from src.loader import list_scenarios, load_scenario
from src.models import OptimizationWeights
from src.plans import enumerate_valid_plans
from src.route_utils import DIRECTION_BK, DIRECTION_KB, format_minutes
from src.scheduler import Scheduler

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "data" / "scenarios"


def test_all_scenarios_produce_valid_schedules():
    for path in list_scenarios(SCENARIOS_DIR):
        scenario = load_scenario(path)
        result = Scheduler(scenario).run()
        assert result.validation_errors == [], (
            f"{path.name}: {result.validation_errors}"
        )
        for bus in result.bus_schedules:
            assert bus.arrival_time_min >= bus.departure_time_min
            assert len(bus.visits) >= scenario.config.min_charges


def test_assignment_route_geometry():
    scenario = load_scenario(SCENARIOS_DIR / "scenario_1.json")
    assert [s.name for s in scenario.route] == [
        "Bengaluru", "A", "B", "C", "D", "Kochi"
    ]
    assert scenario.route[-1].distance_km == 540
    assert scenario.route[0].has_charging is False
    assert scenario.route[-1].has_charging is False
    assert len(scenario.chargers) == 4


def test_valid_charging_plans_exist():
    scenario = load_scenario(SCENARIOS_DIR / "scenario_1.json")
    bk = enumerate_valid_plans(
        scenario.route, DIRECTION_BK, scenario.config.max_range_km
    )
    kb = enumerate_valid_plans(
        scenario.route, DIRECTION_KB, scenario.config.max_range_km
    )
    assert len(bk) >= 2
    assert len(kb) >= 2
    for plan in bk:
        assert len(plan) >= 2


def test_scenario_bus_counts():
    assert len(load_scenario(SCENARIOS_DIR / "scenario_1.json").buses) == 20
    assert len(load_scenario(SCENARIOS_DIR / "scenario_2.json").buses) == 20
    assert len(load_scenario(SCENARIOS_DIR / "scenario_3.json").buses) == 14
    assert len(load_scenario(SCENARIOS_DIR / "scenario_4.json").buses) == 20
    assert len(load_scenario(SCENARIOS_DIR / "scenario_5.json").buses) == 20


def test_scenario_4_operator_weight():
    scenario = load_scenario(SCENARIOS_DIR / "scenario_4.json")
    assert scenario.weights.operator == 2.0
    kpn_bk = sum(
        1
        for b in scenario.buses
        if b.direction == DIRECTION_BK and b.operator_id == "kpn"
    )
    assert kpn_bk == 8


def test_scenario_5_departure_times():
    scenario = load_scenario(SCENARIOS_DIR / "scenario_5.json")
    bk_times = [
        format_minutes(b.departure_time_min)
        for b in scenario.buses
        if b.direction == DIRECTION_BK
    ]
    assert bk_times[0] == "19:00"
    assert bk_times[-1] == "20:12"
    assert "19:64" not in bk_times


def test_weights_affect_congested_scenario():
    from dataclasses import replace

    scenario = load_scenario(SCENARIOS_DIR / "scenario_5.json")
    individual_heavy = replace(
        scenario,
        weights=OptimizationWeights.from_dict(
            {"individual": 3.0, "operator": 0.1, "overall": 1.0}
        ),
    )
    op_heavy = replace(
        scenario,
        weights=OptimizationWeights.from_dict(
            {"individual": 0.1, "operator": 3.0, "overall": 1.0}
        ),
    )

    r_ind = Scheduler(individual_heavy).run()
    r_op = Scheduler(op_heavy).run()
    waits_ind = sorted(b.total_wait_min for b in r_ind.bus_schedules)
    waits_op = sorted(b.total_wait_min for b in r_op.bus_schedules)
    orders_differ = any(
        a.charge_order != b.charge_order
        for a, b in zip(r_ind.station_schedules, r_op.station_schedules)
    )
    assert max(waits_ind) > 0
    assert waits_ind != waits_op or orders_differ
