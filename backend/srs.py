"""Spaced repetition with the SM-2 algorithm (SuperMemo 2, Wozniak 1987), the scheduler behind Anki's classic mode.

Each card has an *ease factor* (EF, starts 2.5), a repetition count and an interval in days. After a review
graded 0..5:

    grade < 3 (a lapse)   repetitions = 0, interval = 1 day            (you forgot it: start over, tomorrow)
    grade >= 3            repetitions 0 -> interval 1 day
                          repetitions 1 -> interval 6 days
                          later          -> interval = round(previous interval * EF)
    always                EF += 0.1 - (5 - g) * (0.08 + (5 - g) * 0.02), never below 1.3

So easy cards drift to long intervals (EF grows), hard ones are seen more often (EF shrinks). This module is
pure: no clock, no database, so it is trivial to test.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

MIN_EF = 1.3
DAY = 86400.0

# The four buttons the UI offers, mapped to SM-2 grades.
GRADES = {"again": 1, "hard": 3, "good": 4, "easy": 5}


@dataclass(frozen=True)
class CardState:
    ef: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0


def review(state: CardState, grade: int) -> CardState:
    """The card's state after a review graded 0 (blackout) .. 5 (perfect)."""
    if not 0 <= grade <= 5:
        raise ValueError("grade must be between 0 and 5")
    ef = max(MIN_EF, state.ef + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    if grade < 3:
        return replace(state, ef=ef, repetitions=0, interval_days=1, lapses=state.lapses + 1)
    if state.repetitions == 0:
        interval = 1
    elif state.repetitions == 1:
        interval = 6
    else:
        interval = max(1, round(state.interval_days * state.ef))  # uses the EF from *before* this review, as in SM-2
    return replace(state, ef=ef, repetitions=state.repetitions + 1, interval_days=interval)


def due_at(now: float, state: CardState) -> float:
    return now + state.interval_days * DAY
