"""Shared MQTT layer for the Vaillant eBusd integration.

A single coordinator subscribes once to every raw ebusd topic, keeps the latest
values, and fans changes out to all entities via the dispatcher. This keeps the
native primitive entities (select/number) and the combined climate/water_heater
entities in sync without each opening its own MQTT subscription.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    CIRCUIT,
    CONF_MQTT_PREFIX,
    DAYS,
    DEFAULT_MQTT_PREFIX,
    DEVICE_NAMES,
    DOMAIN,
    HMU_STATE_SUFFIX,
    SCALAR_TOPICS,
    TIMER_TOPICS,
)

_LOGGER = logging.getLogger(__name__)


class VaillantCoordinator:
    """Owns the MQTT subscriptions and the cached ebusd state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._mqtt_prefix = entry.data.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX)
        self._base = f"{self._mqtt_prefix}/{CIRCUIT}"
        # scalar topic name -> latest value (str | float)
        self.data: dict[str, Any] = {}
        # timer name -> {day -> {"from": .., "to": .., "from_2": .., ...}}
        self.timers: dict[str, dict[str, dict]] = {t: {} for t in TIMER_TOPICS}
        # raw hmu state string ("heating" / "cooling" / "ready" / ...)
        self.hmu_state: str | None = None
        self._unsubs: list[Callable[[], None]] = []

    @property
    def signal(self) -> str:
        """Dispatcher signal fired whenever any cached value changes."""
        return f"{DOMAIN}_{self.entry.entry_id}_update"

    # -- setup / teardown ---------------------------------------------------
    async def async_setup(self) -> None:
        for name in SCALAR_TOPICS:
            self._unsubs.append(
                await mqtt.async_subscribe(
                    self.hass, f"{self._base}/{name}", self._make_scalar_handler(name)
                )
            )
        self._unsubs.append(
            await mqtt.async_subscribe(
                self.hass, f"{self._mqtt_prefix}/{HMU_STATE_SUFFIX}", self._on_hmu_state
            )
        )
        for timer in TIMER_TOPICS:
            for day in DAYS:
                self._unsubs.append(
                    await mqtt.async_subscribe(
                        self.hass,
                        f"{self._base}/{timer}_{day}",
                        self._make_timer_handler(timer, day),
                    )
                )

    def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    # -- message handlers ---------------------------------------------------
    def _make_scalar_handler(self, name: str):
        @callback
        def handler(msg) -> None:
            value = self._parse_value(msg.payload)
            if value is not None:
                self.data[name] = value
                self._notify()

        return handler

    def _make_timer_handler(self, timer: str, day: str):
        @callback
        def handler(msg) -> None:
            try:
                parsed = json.loads(msg.payload)
            except (json.JSONDecodeError, TypeError):
                return
            if isinstance(parsed, dict):
                self.timers[timer][day] = parsed
                self._notify()

        return handler

    @callback
    def _on_hmu_state(self, msg) -> None:
        try:
            self.hmu_state = str(json.loads(msg.payload)["state"])
            self._notify()
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    @staticmethod
    def _parse_value(payload) -> Any:
        """Extract a scalar from an ebusd payload (``{"value": x}`` or raw)."""
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return payload or None
        if isinstance(parsed, dict):
            return parsed.get("value")
        return parsed

    # -- accessors ----------------------------------------------------------
    def get(self, name: str) -> Any:
        return self.data.get(name)

    def get_float(self, name: str) -> float | None:
        value = self.data.get(name)
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    def get_str(self, name: str) -> str | None:
        value = self.data.get(name)
        return str(value) if value is not None else None

    def get_timer_day(self, timer: str, day: str) -> dict | None:
        return self.timers.get(timer, {}).get(day)

    # -- publishing ---------------------------------------------------------
    async def async_publish_scalar(self, name: str, value: Any) -> None:
        await mqtt.async_publish(
            self.hass, f"{self._base}/{name}/set", json.dumps({"value": value})
        )

    async def async_publish_timer(self, timer: str, day: str, payload: dict) -> None:
        await mqtt.async_publish(
            self.hass, f"{self._base}/{timer}_{day}/set", json.dumps(payload)
        )


class VaillantEntity(Entity):
    """Base entity that reads from the coordinator and refreshes via dispatcher."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: VaillantCoordinator, device: str) -> None:
        self.coordinator = coordinator
        self._device = device

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry.entry_id}_{self._device}")},
            name=DEVICE_NAMES[self._device],
            manufacturer="Vaillant",
            model="ebusd MQTT Bridge",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.coordinator.signal, self.async_write_ha_state
            )
        )
