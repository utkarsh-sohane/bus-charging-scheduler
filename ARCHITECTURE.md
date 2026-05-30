# Architecture

## System overview

![High-Level System Architecture](High-Level%20System%20Architecture.png)

Three layers:

| Layer | Components | Role |
|-------|------------|------|
| **Data** | Scenario files, world config, weights | Route, buses, operators, tunable weights (5 scenarios shipped) |
| **Engine** | Loader → Plan → Event simulator → Cost function | Parse, assign stations, simulate queues, score conflicts |
| **UI** | Streamlit | Scenario input, per-bus timetable, per-station queue; scenario change re-runs the engine |

---

## Engine flow

![Scheduler flowchart](flowchart.png)

Discrete-event simulation: valid plans are enumerated per bus (≥2 stops, each leg ≤240 km), then a priority queue drives arrivals. When a charger is busy, waiting buses are scored with scenario weights (`individual`, `operator`, `overall`) and the highest-priority bus is dispatched.

---

## Approach: two-phase rule-based scheduler

The scheduler splits the problem into two phases:

1. **Plan selection** (`src/plans.py`) — Before simulation, each bus is assigned a *valid charging plan*: an ordered list of stations (A–D) such that every leg is ≤ 240 km and at least 2 charges occur. All valid plans are enumerated; the plan with the lowest projected station overlap (given buses already assigned) is chosen.

2. **Event-driven simulation** (`src/scheduler.py`) — Buses depart at their scheduled times and travel along the route. When a bus reaches a planned charging stop, it joins the station queue. When a charger frees, **weighted scoring** picks the next bus. This separates *where* to charge (plan) from *when* to charge (queue resolution).

### Why this fits

| Requirement | How it is handled |
|-------------|-------------------|
| Choose charging stations | Enumerate valid plans; pick per bus before sim |
| Hard constraints | Validation + plan feasibility checks |
| Configurable weights | Scenario JSON → `ScoringEngine` |
| Bidirectional travel | `direction` on each bus; route defined once (BK order) |
| Explainability | Each bus shows its plan + timeline in the UI |
| Extensibility | New rules = new `ScoringRule` class + weight key |

Alternatives considered:
- **Pure greedy (farthest reachable)** — Valid but does not satisfy “choose stations.”
- **Full MILP/CP-SAT** — Overkill for 20 buses; harder to extend with soft rules live.
- **End-to-end RL** — Not explainable or tunable via JSON weights.

---

## Data model

Scenarios are self-contained JSON files. The engine never hardcodes route topology or fleet size.

```json
{
  "route": [
    {"id": "bengaluru", "distance_km": 0, "has_charging": false},
    {"id": "A", "distance_km": 100, "has_charging": true},
    ...
  ],
  "chargers": [{"id": "A_c1", "station_id": "A"}],
  "operators": [{"id": "kpn", "name": "KPN"}],
  "buses": [{
    "id": "bus-BK-01",
    "operator_id": "kpn",
    "direction": "bengaluru_to_kochi",
    "departure_time": "19:00"
  }],
  "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
  "config": {"max_range_km": 240, "min_charges": 2, "charge_duration_min": 25}
}
```

### Key design choices

- **`has_charging: false` on endpoints** — Bengaluru/Kochi are not in the scheduling problem; buses depart full.
- **`direction` on buses** — Same route definition serves both directions; KB buses traverse indices in reverse.
- **`departure_time` as `"HH:MM"`** — Human-readable in scenario files; parsed to minutes internally.
- **Chargers as a separate list** — Station can have 0, 1, or N chargers without schema change.
- **Weights in scenario, not code** — One obvious place to tune per scenario.

---

## Scoring framework

Queue conflicts use **lexicographic scoring**: rules are ordered by weight (highest first); the bus with the best tuple wins. Each rule implements `ScoringRule` with a `name` matching a weight key in the scenario file.

### Change a weight (example)

In `data/scenarios/scenario_4.json`:

```json
"weights": { "individual": 1.0, "operator": 2.0, "overall": 1.0 }
```

Weights are a free-form map — add new keys when you add new rules.

### Add a rule (example)

```python
# src/scoring/priority.py
class PriorityBusRule(ScoringRule):
    name = "priority"
    def score(self, context: ScoringContext) -> float:
        return 1.0 if context.bus_id in PRIORITY_IDS else 0.0
```

Register in `DEFAULT_RULES`, add `"priority": 1.0` to scenario weights.

---

## Anticipated changes (data-only, no engine rewrite)

| Future change | Data change | Code change |
|---------------|-------------|-------------|
| Add station E | Add route stop + charger | None |
| Double chargers at B | Add `"B_c2"` to chargers | None |
| Change segment distance | Edit `distance_km` | None |
| New operator | Add to `operators` | None |
| More buses | Add to `buses` | None |
| Second route | New scenario file | None |
| Priority buses | Add weight + rule class | Small: one rule file |
| Time-of-day pricing | Add weight + rule class | Small: one rule file |
| Station outage | `"has_charging": false` on stop | None |
| Driver shift limits | Add rule + config field | Small: one rule file |

The route/station/charger/bus/weight separation is intentional so future changes (more stations, extra chargers, new operators) are mostly JSON edits.

---

## Simulation flow

See the [engine flowchart](#engine-flow) above. In code:

1. Load scenario JSON (`src/loader.py`)
2. Assign charging plan per bus (`src/plans.py`)
3. Seed event queue and simulate (`src/scheduler.py`)
4. Validate hard constraints (`src/validation.py`)
5. Return output model to Streamlit (`app.py`)

---

## Assumptions

1. Constant speed: 60 km/h ⇒ travel minutes = distance km.
2. Full charge always restores 240 km range.
3. Charging always takes exactly 25 minutes.
4. Buses never skip route order (no backtracking).
5. Plan selection uses projected overlap heuristic; queue order uses weighted scoring at runtime.
6. Valid plans require ≥ 2 charges for the 540 km route.
