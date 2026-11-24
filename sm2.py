"""Classic SuperMemo SM-2 scheduler.

quality is an integer from 0 to 5. Below 3 means the card was forgotten.
"""

from __future__ import annotations


def schedule(quality: int, repetitions: int, ease: float, interval: int) -> tuple[int, float, int]:
    if quality < 0 or quality > 5:
        raise ValueError("quality must be between 0 and 5")

    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease < 1.3:
        ease = 1.3

    if quality < 3:
        return 0, round(ease, 4), 1

    if repetitions <= 0:
        next_interval = 1
    elif repetitions == 1:
        next_interval = 6
    else:
        next_interval = max(1, round(interval * ease))

    return repetitions + 1, round(ease, 4), next_interval
