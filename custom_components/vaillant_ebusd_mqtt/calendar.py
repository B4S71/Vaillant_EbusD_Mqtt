"""Weekly planners exposed as two-way Calendar entities.

Each ebusd timer (heating / cooling / hot water / circulation) becomes a calendar
whose events are the daily comfort windows, repeating every week. Creating,
editing or deleting an event rewrites the corresponding ebusd ``*Timer_{Day}``
schedule. Because the underlying schedule is a fixed weekly pattern, edits always
apply to that weekday in every week (there are no one-off occurrences in ebusd),
and a day may hold at most three windows.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DEVICE_HEATING,
    DEVICE_HOT_WATER,
    DOMAIN,
    MAX_SLOTS,
    T_CIRC_TIMER,
    T_COOLING_TIMER,
    T_HEATING_TIMER,
    T_HWC_TIMER,
    WEEKDAY_TO_DAY,
)
from .coordinator import VaillantCoordinator, VaillantEntity
from .timeprog import Slot, payload_from_slots, slots_from_day


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VaillantCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            VaillantTimerCalendar(
                coordinator, DEVICE_HEATING, "heating_schedule",
                "Heating schedule", T_HEATING_TIMER, "Heating",
            ),
            VaillantTimerCalendar(
                coordinator, DEVICE_HEATING, "cooling_schedule",
                "Cooling schedule", T_COOLING_TIMER, "Cooling",
            ),
            VaillantTimerCalendar(
                coordinator, DEVICE_HOT_WATER, "hot_water_schedule",
                "Hot water schedule", T_HWC_TIMER, "Hot water",
            ),
            VaillantTimerCalendar(
                coordinator, DEVICE_HOT_WATER, "circulation_schedule",
                "Circulation schedule", T_CIRC_TIMER, "Circulation",
            ),
        ]
    )


def _to_dt(day: date, hhmm: str) -> datetime:
    """Build a local-time datetime; ``24:00`` rolls over to next midnight."""
    hour, minute = (int(p) for p in hhmm.split(":"))
    if hour >= 24:
        base = datetime.combine(day + timedelta(days=1), time(0, 0))
    else:
        base = datetime.combine(day, time(hour, minute))
    return base.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)


def _to_hhmm(value: datetime, *, is_end: bool, ref_day: date) -> str:
    """Format a datetime as ``HH:MM`` (midnight next day -> ``24:00``)."""
    local = dt_util.as_local(value)
    if is_end and local.date() > ref_day and local.time() == time(0, 0):
        return "24:00"
    return local.strftime("%H:%M")


class VaillantTimerCalendar(VaillantEntity, CalendarEntity):
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT
        | CalendarEntityFeature.DELETE_EVENT
        | CalendarEntityFeature.UPDATE_EVENT
    )

    def __init__(
        self,
        coordinator: VaillantCoordinator,
        device: str,
        key: str,
        name: str,
        timer: str,
        summary: str,
    ) -> None:
        super().__init__(coordinator, device)
        self._timer = timer
        self._summary = summary
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    # -- uid helpers --------------------------------------------------------
    def _uid(self, day: str, idx: int, day_date: date) -> str:
        return f"{self._timer}|{day}|{idx}|{day_date.isoformat()}"

    @staticmethod
    def _decode_uid(uid: str) -> tuple[str, int]:
        parts = uid.split("|")
        return parts[1], int(parts[2])

    # -- read ---------------------------------------------------------------
    def _events_for_date(self, day_date: date) -> list[CalendarEvent]:
        day = WEEKDAY_TO_DAY[day_date.weekday()]
        slots = slots_from_day(self.coordinator.get_timer_day(self._timer, day))
        events: list[CalendarEvent] = []
        for idx, (start, end) in enumerate(slots):
            events.append(
                CalendarEvent(
                    start=_to_dt(day_date, start),
                    end=_to_dt(day_date, end),
                    summary=self._summary,
                    uid=self._uid(day, idx, day_date),
                )
            )
        return events

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        today = now.date()
        for offset in range(0, 8):
            for ev in self._events_for_date(today + timedelta(days=offset)):
                if ev.end > now:
                    return ev
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        current = dt_util.as_local(start_date).date()
        last = dt_util.as_local(end_date).date()
        while current <= last:
            for ev in self._events_for_date(current):
                if ev.end > start_date and ev.start < end_date:
                    events.append(ev)
            current += timedelta(days=1)
        return events

    # -- write --------------------------------------------------------------
    def _current_slots(self, day: str) -> list[Slot]:
        return slots_from_day(self.coordinator.get_timer_day(self._timer, day))

    async def _write_day(self, day: str, slots: list[Slot]) -> None:
        if len(slots) > MAX_SLOTS:
            raise HomeAssistantError(
                f"ebusd allows at most {MAX_SLOTS} windows per day"
            )
        slots = sorted(slots, key=lambda s: s[0])
        await self.coordinator.async_publish_timer(
            self._timer, day, payload_from_slots(slots)
        )

    @staticmethod
    def _slot_from_event(dtstart: datetime, dtend: datetime) -> tuple[str, Slot]:
        local_start = dt_util.as_local(dtstart)
        day = WEEKDAY_TO_DAY[local_start.weekday()]
        ref_day = local_start.date()
        start = _to_hhmm(dtstart, is_end=False, ref_day=ref_day)
        end = _to_hhmm(dtend, is_end=True, ref_day=ref_day)
        return day, (start, end)

    async def async_create_event(self, **kwargs) -> None:
        dtstart = kwargs["dtstart"]
        dtend = kwargs["dtend"]
        if not isinstance(dtstart, datetime) or not isinstance(dtend, datetime):
            raise HomeAssistantError("All-day events are not supported")
        day, slot = self._slot_from_event(dtstart, dtend)
        await self._write_day(day, [*self._current_slots(day), slot])

    async def async_delete_event(
        self, uid: str, recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        day, idx = self._decode_uid(uid)
        slots = self._current_slots(day)
        if 0 <= idx < len(slots):
            del slots[idx]
            await self._write_day(day, slots)

    async def async_update_event(
        self, uid: str, event: dict, recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        old_day, idx = self._decode_uid(uid)
        new_day, slot = self._slot_from_event(event["dtstart"], event["dtend"])

        old_slots = self._current_slots(old_day)
        if old_day == new_day:
            if 0 <= idx < len(old_slots):
                old_slots[idx] = slot
            await self._write_day(new_day, old_slots)
            return
        # moved to a different weekday: drop from old, append to new
        if 0 <= idx < len(old_slots):
            del old_slots[idx]
        await self._write_day(old_day, old_slots)
        await self._write_day(new_day, [*self._current_slots(new_day), slot])
