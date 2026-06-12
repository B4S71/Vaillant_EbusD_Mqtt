from __future__ import annotations

import json

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_ENTITY_PREFIX, CONF_MQTT_PREFIX, DAYS, DOMAIN, SLOT_SUFFIXES

_EMPTY = "-:-"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([VaillantHotWater(config_entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_hot_water_time_program",
        {
            vol.Required("day"): vol.In(DAYS),
            vol.Required("slots"): vol.All(
                cv.ensure_list,
                [vol.Schema({vol.Required("from"): str, vol.Required("to"): str})],
            ),
        },
        "async_set_time_program",
    )
    platform.async_register_entity_service(
        "trigger_legionella_protection",
        {},
        "async_trigger_legionella_protection",
    )


class VaillantHotWater(WaterHeaterEntity):
    """Water heater entity backed by existing ebusd_vaillant select/sensor entities."""

    _attr_should_poll = False
    _attr_name = "Vaillant Warmwasser"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = ["off", "auto", "day", "night"]
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_min_temp = 40.0
    _attr_max_temp = 70.0

    def __init__(self, config_entry: ConfigEntry) -> None:
        ep = config_entry.data[CONF_ENTITY_PREFIX]
        self._mp = config_entry.data[CONF_MQTT_PREFIX]
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_hot_water"

        self._mode_id = f"select.{ep}_ebusd_700_hwcopmode"
        self._temp_id = f"sensor.{ep}_ebusd_700_hwcstoragetemp"
        self._target_id = f"sensor.{ep}_ebusd_hmu_setmode_hwctempdesired"
        self._timer_prefix = f"sensor.{ep}_ebusd_700_hwctimer"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="Vaillant ebusd",
            manufacturer="Vaillant",
            model="ebusd MQTT Bridge",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._mode_id, self._temp_id, self._target_id],
                self._on_state_change,
            )
        )

    @callback
    def _on_state_change(self, event) -> None:
        self.async_write_ha_state()

    def _float_state(self, entity_id: str) -> float | None:
        s = self.hass.states.get(entity_id)
        if s and s.state not in ("unknown", "unavailable"):
            try:
                return float(s.state)
            except ValueError:
                pass
        return None

    @property
    def current_operation(self) -> str:
        s = self.hass.states.get(self._mode_id)
        if s is None or s.state in ("unknown", "unavailable"):
            return "off"
        return s.state

    @property
    def current_temperature(self) -> float | None:
        return self._float_state(self._temp_id)

    @property
    def target_temperature(self) -> float | None:
        val = self._float_state(self._target_id)
        return val if val is not None and val > 0 else None

    @property
    def extra_state_attributes(self) -> dict:
        timer: dict[str, list] = {}
        for day in DAYS:
            slots = []
            for suffix in SLOT_SUFFIXES:
                f = self.hass.states.get(f"{self._timer_prefix}_{day.lower()}_from{suffix}")
                t = self.hass.states.get(f"{self._timer_prefix}_{day.lower()}_to{suffix}")
                if (
                    f and f.state not in ("unknown", "unavailable", _EMPTY)
                    and t and t.state not in ("unknown", "unavailable", _EMPTY)
                ):
                    slots.append({"from": f.state, "to": t.state})
            timer[day] = slots
        return {"time_program": timer}

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self._mode_id, "option": operation_mode},
            blocking=True,
        )

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get("temperature")
        if temp is not None:
            await mqtt.async_publish(
                self.hass,
                f"{self._mp}/hmu/SetMode/set",
                json.dumps({"hwctempdesired": float(temp)}),
            )

    async def async_set_time_program(self, day: str, slots: list[dict]) -> None:
        payload: dict = {}
        for i, suffix in enumerate(SLOT_SUFFIXES):
            payload[f"from{suffix}"] = slots[i]["from"] if i < len(slots) else _EMPTY
            payload[f"to{suffix}"] = slots[i]["to"] if i < len(slots) else _EMPTY
        await mqtt.async_publish(
            self.hass, f"{self._mp}/700/HwcTimer_{day}/set", json.dumps(payload)
        )

    async def async_trigger_legionella_protection(self) -> None:
        await mqtt.async_publish(
            self.hass,
            f"{self._mp}/hmu/SetMode/set",
            json.dumps({"hwctempdesired": 70}),
        )
