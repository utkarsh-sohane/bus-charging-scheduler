from src.scoring.base import ScoringContext, ScoringRule


class OverallEfficiencyRule(ScoringRule):
    """Prefer assignments that reduce aggregate network waiting."""

    name = "overall"

    def score(self, context: ScoringContext) -> float:
        if context.network_total_wait_min <= 0 and context.pending_wait_count <= 0:
            return 1.0
        # Clearing a bus that has waited longest at the station helps total delay
        station_pressure = context.wait_time_min
        network_avg = context.network_total_wait_min / max(
            1, context.pending_wait_count
        )
        return (station_pressure + 1.0) / (network_avg + 1.0)
