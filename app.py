"""Streamlit UI for the Bus Charging Scheduler."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.loader import list_scenarios, load_scenario
from src.route_utils import format_minutes
from src.scheduler import Scheduler

SCENARIOS_DIR = Path(__file__).parent / "data" / "scenarios"

DIRECTION_LABELS = {
    "bengaluru_to_kochi": "Bengaluru → Kochi",
    "kochi_to_bengaluru": "Kochi → Bengaluru",
}


@st.cache_data(show_spinner=False)
def run_scheduler(scenario_path: str) -> dict:
    scenario = load_scenario(scenario_path)
    result = Scheduler(scenario).run()
    return {"scenario": scenario, "result": result}


def main() -> None:
    st.set_page_config(
        page_title="Bus Charging Scheduler",
        page_icon="🚌",
        layout="wide",
    )
    st.title("Bus Charging Scheduler")
    st.caption("Bengaluru ↔ Kochi intercity electric bus charging plans")

    paths = list_scenarios(SCENARIOS_DIR)
    if not paths:
        st.error("No scenario files found in data/scenarios/")
        return

    labels: list[str] = []
    path_by_label: dict[str, str] = {}
    for p in paths:
        sc = load_scenario(p)
        labels.append(sc.name)
        path_by_label[sc.name] = str(p)

    selected = st.selectbox("Scenario", labels, index=0)
    data = run_scheduler(path_by_label[selected])
    scenario = data["scenario"]
    result = data["result"]

    if result.validation_errors:
        st.warning("Validation: " + "; ".join(result.validation_errors[:5]))
    else:
        st.success("Valid schedule — range, charger, and timing constraints satisfied.")

    tab_scenario, tab_buses, tab_stations = st.tabs(
        ["Scenario", "Per-Bus", "Per-Station"]
    )

    with tab_scenario:
        st.subheader(scenario.name)
        st.write(scenario.description)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Route**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Station": s.name,
                            "Distance (km)": s.distance_km,
                            "Scheduled": "Yes" if s.has_charging else "Endpoint only",
                        }
                        for s in scenario.route
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("**Chargers (A–D only)**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Station": c.station_id, "Charger": c.id}
                        for c in scenario.chargers
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

        with col2:
            w = scenario.weights
            st.markdown("**Optimization weights**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Dimension": k, "Weight": v}
                        for k, v in sorted(w.values.items())
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

            cfg = scenario.config
            st.markdown("**Configuration**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Parameter": "Max range (km)", "Value": cfg.max_range_km},
                        {"Parameter": "Min charges", "Value": cfg.min_charges},
                        {"Parameter": "Charge time (min)", "Value": cfg.charge_duration_min},
                        {"Parameter": "Speed (km/h)", "Value": cfg.speed_kmph},
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("**Input — bus departures**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Bus": b.id,
                        "Operator": next(
                            (o.name for o in scenario.operators if o.id == b.operator_id),
                            b.operator_id,
                        ),
                        "Direction": DIRECTION_LABELS.get(b.direction, b.direction),
                        "Departure": format_minutes(b.departure_time_min),
                    }
                    for b in scenario.buses
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tab_buses:
        st.subheader("Per-bus timetable")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Bus": bs.bus_id,
                        "Operator": bs.operator_name,
                        "Direction": DIRECTION_LABELS.get(bs.direction, bs.direction),
                        "Plan": " → ".join(bs.charging_plan),
                        "Charges": len(bs.visits),
                        "Wait (min)": round(bs.total_wait_min, 1),
                        "Arrival": format_minutes(bs.arrival_time_min),
                    }
                    for bs in result.bus_schedules
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        for bs in result.bus_schedules:
            with st.expander(f"{bs.bus_id} — full timeline"):
                st.write(
                    f"Departure **{format_minutes(bs.departure_time_min)}** → "
                    f"Arrival **{format_minutes(bs.arrival_time_min)}** · "
                    f"Plan: **{' → '.join(bs.charging_plan)}**"
                )
                if not bs.visits:
                    st.write("No charging stops.")
                    continue
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Station": v.station_name,
                                "Arrival": format_minutes(v.arrival_time_min),
                                "Wait (min)": round(v.wait_time_min, 1),
                                "Charge start": format_minutes(v.charge_start_min),
                                "Charge end": format_minutes(v.charge_end_min),
                            }
                            for v in bs.visits
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    with tab_stations:
        st.subheader("Per-station charge order")
        for ss in result.station_schedules:
            order = ", ".join(ss.charge_order) if ss.charge_order else "(none)"
            st.markdown(f"**Station {ss.station_name}** — {order}")
            for charger_id, entries in ss.charger_timelines.items():
                if entries:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Charger": charger_id,
                                    "Bus": e.bus_id,
                                    "Start": format_minutes(e.start_min),
                                    "End": format_minutes(e.end_min),
                                }
                                for e in entries
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )


if __name__ == "__main__":
    main()
