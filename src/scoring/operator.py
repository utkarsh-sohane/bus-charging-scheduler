from src.scoring.base import ScoringContext, ScoringRule


class OperatorFairnessRule(ScoringRule):
    """Prefer operators with less fleet waiting and fewer completed charges."""

    name = "operator"

    def score(self, context: ScoringContext) -> float:
        if context.operator_bus_count <= 0:
            return 0.5
        avg_wait = context.operator_total_wait_min / context.operator_bus_count
        wait_factor = 1.0 / (1.0 + avg_wait)
        charge_factor = 1.0 / (1.0 + context.operator_charges_so_far)
        return 0.6 * wait_factor + 0.4 * charge_factor
