"""Run the scheduler from the command line (no UI)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.loader import list_scenarios, load_scenario
from src.route_utils import format_minutes
from src.scheduler import Scheduler

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "data" / "scenarios"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bus Charging Scheduler CLI")
    parser.add_argument(
        "scenario",
        nargs="?",
        help="Scenario id (e.g. scenario_1) or path to JSON file",
    )
    parser.add_argument(
        "--list", action="store_true", help="List available scenarios"
    )
    args = parser.parse_args(argv)

    if args.list:
        for p in list_scenarios(SCENARIOS_DIR):
            sc = load_scenario(p)
            print(f"  {sc.id}: {sc.name} ({len(sc.buses)} buses)")
        return 0

    if not args.scenario:
        parser.print_help()
        return 1

    path = Path(args.scenario)
    if not path.exists():
        path = SCENARIOS_DIR / f"{args.scenario}.json"
    if not path.exists():
        print(f"Scenario not found: {args.scenario}", file=sys.stderr)
        return 1

    scenario = load_scenario(path)
    result = Scheduler(scenario).run()

    print(f"\n{scenario.name}")
    print(f"Buses: {len(result.bus_schedules)}")
    if result.validation_errors:
        print(f"VALIDATION ERRORS ({len(result.validation_errors)}):")
        for e in result.validation_errors:
            print(f"  - {e}")
    else:
        print("Validation: OK")

    print("\nPer-bus summary:")
    for bs in result.bus_schedules:
        plan = " -> ".join(bs.charging_plan)
        print(
            f"  {bs.bus_id}  dep={format_minutes(bs.departure_time_min)}"
            f"  arr={format_minutes(bs.arrival_time_min)}"
            f"  wait={bs.total_wait_min:.0f}min"
            f"  plan={plan}"
        )

    print("\nPer-station charge order:")
    for ss in result.station_schedules:
        order = ", ".join(ss.charge_order) if ss.charge_order else "(none)"
        print(f"  {ss.station_name}: {order}")

    return 1 if result.validation_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
