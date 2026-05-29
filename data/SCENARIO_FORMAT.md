# Scenario file format

Each scenario is a self-contained JSON file under `data/scenarios/`. The scheduler reads this file and produces a charging plan — no code changes required for new scenarios.

## Top-level fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique id, e.g. `scenario_1` |
| `name` | yes | Display name in the UI dropdown |
| `description` | no | Short explanation of the test case |
| `config` | no | Physical constants (defaults match assignment) |
| `weights` | no | Optimization weights for queue scoring |
| `route` | yes | Ordered list of stops |
| `chargers` | yes | Charger inventory |
| `operators` | yes | Fleet operators |
| `buses` | yes | Departure schedule |

## Route stops

```json
{
  "id": "A",
  "name": "A",
  "distance_km": 100,
  "has_charging": true
}
```

- `distance_km` — cumulative distance from Bengaluru (assignment route is 540 km total).
- `has_charging: false` on endpoints — Bengaluru and Kochi are **not** part of scheduling; buses depart fully charged.

Assignment route:

| Stop | km |
|------|-----|
| Bengaluru | 0 |
| A | 100 |
| B | 220 |
| C | 320 |
| D | 440 |
| Kochi | 540 |

## Chargers

```json
{"id": "A_c1", "station_id": "A"}
```

Add more entries to model multiple chargers at one station — no engine changes needed.

## Buses

```json
{
  "id": "bus-BK-01",
  "operator_id": "kpn",
  "direction": "bengaluru_to_kochi",
  "departure_time": "19:00"
}
```

Directions:
- `bengaluru_to_kochi` — travels toward Kochi
- `kochi_to_bengaluru` — travels toward Bengaluru (same route, reversed)

`departure_time` uses `"HH:MM"` 24-hour format.

## Weights

```json
"weights": {
  "individual": 1.0,
  "operator": 2.0,
  "overall": 1.0
}
```

Each key maps to a `ScoringRule` in `src/scoring/`. Add a new rule class + key here to extend optimization.

## Config

```json
"config": {
  "max_range_km": 240,
  "charge_duration_min": 25,
  "speed_kmph": 60,
  "min_charges": 2
}
```

At 60 km/h, travel time in minutes equals distance in km (100 km → 100 min).

## Anticipated extensions (data only)

| Change | How |
|--------|-----|
| New station | Add route stop + charger |
| Double chargers | Add second charger with same `station_id` |
| Longer route | Add stops with updated `distance_km` |
| New operator | Add to `operators` |
| Disable station | Set `has_charging: false` |
| New scenario | Drop a new JSON file in this folder |

See `ARCHITECTURE.md` for design rationale.
