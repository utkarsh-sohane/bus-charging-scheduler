from __future__ import annotations

from src.models import OptimizationWeights
from src.scoring.base import ScoringContext, ScoringRule
from src.scoring.individual import IndividualFairnessRule
from src.scoring.operator import OperatorFairnessRule
from src.scoring.overall import OverallEfficiencyRule

DEFAULT_RULES: list[ScoringRule] = [
    IndividualFairnessRule(),
    OperatorFairnessRule(),
    OverallEfficiencyRule(),
]


class ScoringEngine:
    """Lexicographic weighted scoring — highest weight dimension breaks ties first."""

    def __init__(
        self,
        weights: OptimizationWeights,
        rules: list[ScoringRule] | None = None,
    ) -> None:
        self.weights = weights
        self.rules = rules if rules is not None else list(DEFAULT_RULES)
        self._rules_by_weight = sorted(
            self.rules,
            key=lambda r: weights.get(r.name, 0.0),
            reverse=True,
        )

    def score_tuple(self, context: ScoringContext) -> tuple[float, ...]:
        parts: list[float] = []
        for rule in self._rules_by_weight:
            if self.weights.get(rule.name, 0.0) > 0:
                parts.append(rule.score(context))
        return tuple(parts) if parts else (0.0,)

    def total_score(self, context: ScoringContext) -> float:
        """Scalar summary for debugging; queue resolution uses score_tuple."""
        t = self.score_tuple(context)
        return sum(t) / len(t) if t else 0.0

    def pick_winner(
        self, contexts: list[ScoringContext]
    ) -> ScoringContext:
        return max(contexts, key=self.score_tuple)
