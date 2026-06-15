"""Helpers to translate between ebusd timer JSON and slot lists.

ebusd represents a day's schedule as up to three windows in a flat dict::

    {"from": "06:00", "to": "21:00", "from_2": "-:-", "to_2": "-:-",
     "from_3": "-:-", "to_3": "-:-"}

with ``-:-`` marking an unused window.
"""
from __future__ import annotations

from .const import EMPTY, SLOT_SUFFIXES

Slot = tuple[str, str]


def slots_from_day(day_data: dict | None) -> list[Slot]:
    """Return the active ``(from, to)`` windows for one day."""
    if not day_data:
        return []
    out: list[Slot] = []
    for suffix in SLOT_SUFFIXES:
        start = day_data.get(f"from{suffix}")
        end = day_data.get(f"to{suffix}")
        if start and end and start != EMPTY and end != EMPTY:
            out.append((start, end))
    return out


def payload_from_slots(slots: list[Slot]) -> dict:
    """Encode windows back into the 6-field ebusd timer payload."""
    payload: dict[str, str] = {}
    for i, suffix in enumerate(SLOT_SUFFIXES):
        if i < len(slots):
            payload[f"from{suffix}"] = slots[i][0]
            payload[f"to{suffix}"] = slots[i][1]
        else:
            payload[f"from{suffix}"] = EMPTY
            payload[f"to{suffix}"] = EMPTY
    return payload
