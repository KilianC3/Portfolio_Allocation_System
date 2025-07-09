from __future__ import annotations

from .politician_sleeves import FollowTheLeaderSleeves


class CapitoSleeve(FollowTheLeaderSleeves):
    """Replicate Shelley Moore Capito's disclosed trades."""

    def __init__(self) -> None:
        super().__init__(["Shelley Moore Capito"])
