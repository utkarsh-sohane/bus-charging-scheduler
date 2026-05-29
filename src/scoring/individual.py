from src.scoring.base import ScoringContext, ScoringRule


class IndividualFairnessRule(ScoringRule):
    """Prefer the bus waiting longest at this station right now."""

    name = "individual"

    def score(self, context: ScoringContext) -> float:
        station_burden = context.wait_time_min
        history = context.total_wait_min
        return 1.0 / (1.0 + station_burden + 0.2 * history)
