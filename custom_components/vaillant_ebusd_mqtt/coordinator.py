from __future__ import annotations

import json
import logging
from collections.abc import Callable

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_HMU_PREFIX,
    CONF_MQTT_PREFIX,
    DAYS,
    SLOT_SUFFIXES,
)

_LOGGER = logging.getLogger(__name__)

# Sentinel for empty slot
_EMPTY = "-:-"


class VaillantEbusdCoordinator:
    """Manages MQTT subscriptions and state for one Vaillant ebusd device."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self._hass = hass
        self._mqtt_prefix: str = config_entry.data[CONF_MQTT_PREFIX]
        self._hmu_prefix: str = config_entry.data[CONF_HMU_PREFIX]

        # Time programs: day -> list of {"from": "HH:MM", "to": "HH:MM"}
        self.cc_timer: dict[str, list[dict]] = {}
        self.hwc_timer: dict[str, list[dict]] = {}

        # SetMode state
        self.hc_mode: str | None = None
        self.disable_hc: bool = False
        self.flow_temp_desired: float | None = None

        self._listeners: list[Callable] = []
        self._unsubscribe: list[Callable] = []

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Subscribe to all relevant MQTT topics."""
        for day in DAYS:
            self._unsubscribe.append(
                await mqtt.async_subscribe(
                    self._hass,
                    f"{self._mqtt_prefix}/CcTimer_{day}",
                    lambda msg, d=day: self._on_timer(self.cc_timer, d, msg),
                    encoding="utf-8",
                )
            )
            self._unsubscribe.append(
                await mqtt.async_subscribe(
                    self._hass,
                    f"{self._mqtt_prefix}/HwcTimer_{day}",
                    lambda msg, d=day: self._on_timer(self.hwc_timer, d, msg),
                    encoding="utf-8",
                )
            )

        self._unsubscribe.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._hmu_prefix}/SetMode",
                self._on_setmode,
                encoding="utf-8",
            )
        )

    async def async_unload(self) -> None:
        for unsub in self._unsubscribe:
            unsub()
        self._unsubscribe.clear()

    # ------------------------------------------------------------------
    # MQTT receive handlers
    # ------------------------------------------------------------------

    @callback
    def _on_timer(self, store: dict, day: str, msg) -> None:
        try:
            data = json.loads(msg.payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Bad JSON on timer topic for %s: %s", day, msg.payload)
            return

        slots = []
        for suffix in SLOT_SUFFIXES:
            from_val = data.get(f"from{suffix}", _EMPTY)
            to_val = data.get(f"to{suffix}", _EMPTY)
            if from_val and from_val != _EMPTY:
                slots.append({"from": from_val, "to": to_val})

        store[day] = slots
        self._notify()

    @callback
    def _on_setmode(self, msg) -> None:
        try:
            data = json.loads(msg.payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Bad JSON on SetMode: %s", msg.payload)
            return

        self.hc_mode = data.get("hcmode")
        self.disable_hc = str(data.get("disablehc", "0")) == "1"
        try:
            self.flow_temp_desired = float(data.get("flowtempdesired", 0)) or None
        except (ValueError, TypeError):
            self.flow_temp_desired = None
        self._notify()

    # ------------------------------------------------------------------
    # MQTT publish helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_timer_payload(slots: list[dict]) -> str:
        payload: dict = {}
        for i, suffix in enumerate(SLOT_SUFFIXES):
            if i < len(slots):
                payload[f"from{suffix}"] = slots[i]["from"]
                payload[f"to{suffix}"] = slots[i]["to"]
            else:
                payload[f"from{suffix}"] = _EMPTY
                payload[f"to{suffix}"] = _EMPTY
        return json.dumps(payload)

    async def async_set_cc_timer(self, day: str, slots: list[dict]) -> None:
        await mqtt.async_publish(
            self._hass,
            f"{self._mqtt_prefix}/CcTimer_{day}/set",
            self._build_timer_payload(slots),
        )

    async def async_set_hwc_timer(self, day: str, slots: list[dict]) -> None:
        await mqtt.async_publish(
            self._hass,
            f"{self._mqtt_prefix}/HwcTimer_{day}/set",
            self._build_timer_payload(slots),
        )

    async def async_set_hc_mode(self, ebusd_mode: str) -> None:
        await mqtt.async_publish(
            self._hass,
            f"{self._hmu_prefix}/SetMode/set",
            json.dumps({"hcmode": ebusd_mode}),
        )

    # ------------------------------------------------------------------
    # Listener management (entities subscribe here)
    # ------------------------------------------------------------------

    @callback
    def async_add_listener(self, listener: Callable) -> Callable:
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in self._listeners:
            listener()
