"""Generate the 5 assignment scenario JSON files."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "scenarios"

ROUTE = [
    {"id": "bengaluru", "name": "Bengaluru", "distance_km": 0, "has_charging": False},
    {"id": "A", "name": "A", "distance_km": 100, "has_charging": True},
    {"id": "B", "name": "B", "distance_km": 220, "has_charging": True},
    {"id": "C", "name": "C", "distance_km": 320, "has_charging": True},
    {"id": "D", "name": "D", "distance_km": 440, "has_charging": True},
    {"id": "kochi", "name": "Kochi", "distance_km": 540, "has_charging": False},
]

CHARGERS = [
    {"id": "A_c1", "station_id": "A"},
    {"id": "B_c1", "station_id": "B"},
    {"id": "C_c1", "station_id": "C"},
    {"id": "D_c1", "station_id": "D"},
]

OPERATORS = [
    {"id": "kpn", "name": "KPN"},
    {"id": "freshbus", "name": "Freshbus"},
    {"id": "flixbus", "name": "Flixbus"},
]

CONFIG = {
    "max_range_km": 240,
    "charge_duration_min": 25,
    "speed_kmph": 60,
    "min_charges": 2,
}

BK = "bengaluru_to_kochi"
KB = "kochi_to_bengaluru"

OPS_CYCLE = ["kpn", "freshbus", "flixbus"]


def t(h: int, m: int = 0) -> str:
    """Format clock time; normalizes minutes >= 60."""
    total = h * 60 + m
    return f"{total // 60:02d}:{total % 60:02d}"


def bk_buses(
    times: list[str],
    operators: list[str] | None = None,
) -> list[dict]:
    ops = operators or [OPS_CYCLE[i % 3] for i in range(len(times))]
    return [
        {
            "id": f"bus-BK-{i + 1:02d}",
            "operator_id": ops[i],
            "direction": BK,
            "departure_time": times[i],
        }
        for i in range(len(times))
    ]


def kb_buses(
    times: list[str],
    operators: list[str] | None = None,
) -> list[dict]:
    ops = operators or [OPS_CYCLE[(i + 1) % 3] for i in range(len(times))]
    return [
        {
            "id": f"bus-KB-{i + 1:02d}",
            "operator_id": ops[i],
            "direction": KB,
            "departure_time": times[i],
        }
        for i in range(len(times))
    ]


def write_scenario(data: dict) -> None:
    path = OUT / f"{data['id']}.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path.name} ({len(data['buses'])} buses)")


def main() -> None:
    every_15 = [t(19, i * 15) for i in range(10)]

    write_scenario(
        {
            "id": "scenario_1",
            "name": "Scenario 1 — Even Spacing",
            "description": "Baseline: buses depart every 15 minutes in each direction from 19:00.",
            "config": CONFIG,
            "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
            "route": ROUTE,
            "chargers": CHARGERS,
            "operators": OPERATORS,
            "buses": bk_buses(every_15) + kb_buses(every_15),
        }
    )

    bunch_times = [
        t(19, 0), t(19, 8), t(19, 16), t(19, 24), t(19, 32),
        t(19, 40), t(19, 48), t(20, 3), t(20, 18), t(20, 33),
    ]

    write_scenario(
        {
            "id": "scenario_2",
            "name": "Scenario 2 — Bunched Start",
            "description": "Tight cluster every 8 min over the first 50 minutes, then spaced out. Heavy early contention.",
            "config": CONFIG,
            "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
            "route": ROUTE,
            "chargers": CHARGERS,
            "operators": OPERATORS,
            "buses": bk_buses(bunch_times) + kb_buses(bunch_times),
        }
    )

    asym_kb_times = [t(19, 0), t(19, 35), t(20, 10), t(20, 45)]
    write_scenario(
        {
            "id": "scenario_3",
            "name": "Scenario 3 — Asymmetric Load",
            "description": "10 buses Bengaluru→Kochi (15 min spacing) and 4 buses Kochi→Bengaluru (wider spacing).",
            "config": CONFIG,
            "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
            "route": ROUTE,
            "chargers": CHARGERS,
            "operators": OPERATORS,
            "buses": bk_buses(every_15) + kb_buses(asym_kb_times),
        }
    )

    # KPN operates 8 of 10 BK buses (assignment spec)
    op_heavy_bk_ops = ["kpn"] * 8 + ["freshbus", "flixbus"]
    write_scenario(
        {
            "id": "scenario_4",
            "name": "Scenario 4 — Operator-Heavy",
            "description": "KPN dominates the Bengaluru→Kochi fleet (8 of 10). Operator weight = 2.0.",
            "config": CONFIG,
            "weights": {"individual": 1.0, "operator": 2.0, "overall": 1.0},
            "route": ROUTE,
            "chargers": CHARGERS,
            "operators": OPERATORS,
            "buses": bk_buses(every_15, op_heavy_bk_ops) + kb_buses(every_15),
        }
    )

    # All 20 buses within 72 minutes: 19:00 .. 20:12 every 8 min
    worst_times = [t(19, i * 8) for i in range(10)]
    worst_bk_ops = [
        "kpn", "freshbus", "flixbus", "kpn", "freshbus",
        "flixbus", "kpn", "freshbus", "flixbus", "kpn",
    ]
    worst_kb_ops = [
        "freshbus", "flixbus", "kpn", "freshbus", "flixbus",
        "kpn", "freshbus", "flixbus", "kpn", "freshbus",
    ]
    write_scenario(
        {
            "id": "scenario_5",
            "name": "Scenario 5 — Worst Case Convergence",
            "description": "All 20 buses within 72 minutes (every 8 min) from both ends. Maximum contention at B and C.",
            "config": CONFIG,
            "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
            "route": ROUTE,
            "chargers": CHARGERS,
            "operators": OPERATORS,
            "buses": bk_buses(worst_times, worst_bk_ops)
            + kb_buses(worst_times, worst_kb_ops),
        }
    )


if __name__ == "__main__":
    main()
