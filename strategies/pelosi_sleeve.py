from __future__ import annotations

from .politician_sleeves import FollowTheLeaderSleeves


class PelosiSleeve(FollowTheLeaderSleeves):
    """Replicate Nancy Pelosi's disclosed trades."""

    def __init__(self) -> None:
        super().__init__(["Nancy Pelosi"])
