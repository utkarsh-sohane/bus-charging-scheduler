from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ScoringContext:
    """Snapshot passed to scoring rules when resolving charger conflicts."""

    bus_id: str
    operator_id: str
    wait_time_min: float
    total_wait_min: float
    operator_total_wait_min: float
    operator_bus_count: int
    operator_charges_so_far: int
    network_total_wait_min: float
    pending_wait_count: int


class ScoringRule(ABC):
    """Pluggable scoring term; higher score = higher priority for charger access."""

    name: str

    @abstractmethod
    def score(self, context: ScoringContext) -> float:
        """Return a normalized score in roughly 0–1 (higher is better)."""
