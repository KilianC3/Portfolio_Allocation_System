from __future__ import annotations

from .politician_sleeves import FollowTheLeaderSleeves


class MuserSleeve(FollowTheLeaderSleeves):
    """Replicate Dan Meuser's disclosed trades."""

    def __init__(self) -> None:
        super().__init__(["Dan Meuser"])
