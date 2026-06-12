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

from .const import CONF_ENTITY_PREFIX, CONF_MQTT_PREFIX, DEFAULT_ENTITY_PREFIX, DAYS, DOMAIN, SLOT_SUFFIXES

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
        self._mp = config_entry.data[CONF_MQTT_PREFIX]
        self._ep = config_entry.data.get(CONF_ENTITY_PREFIX, DEFAULT_ENTITY_PREFIX)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_hot_water"

        self._op_mode_raw: str | None = None
        self._current_temp: float | None = None
        self._target_temp: float | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="Vaillant ebusd",
            manufacturer="Vaillant",
            model="ebusd MQTT Bridge",
        )

    async def async_added_to_hass(self) -> None:
        base = f"{self._mp}/700"
        for topic, handler in [
            (f"{base}/HwcOpMode",      self._on_op_mode),
            (f"{base}/HwcStorageTemp", self._on_current_temp),
            (f"{base}/HwcTempDesired", self._on_target_temp),
        ]:
            self.async_on_remove(
                await mqtt.async_subscribe(self.hass, topic, handler)
            )

    def _val(self, msg) -> str | float | None:
        try:
            return json.loads(msg.payload)["value"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _float_val(self, msg) -> float | None:
        v = self._val(msg)
        try:
            return float(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    @callback
    def _on_op_mode(self, msg) -> None:
        v = self._val(msg)
        if v is not None:
            self._op_mode_raw = str(v)
        self.async_write_ha_state()

    @callback
    def _on_current_temp(self, msg) -> None:
        v = self._float_val(msg)
        if v is not None:
            self._current_temp = v
        self.async_write_ha_state()

    @callback
    def _on_target_temp(self, msg) -> None:
        v = self._float_val(msg)
        if v is not None and v > 0:
            self._target_temp = v
        self.async_write_ha_state()

    @property
    def current_operation(self) -> str:
        return self._op_mode_raw or "off"

    @property
    def current_temperature(self) -> float | None:
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        return self._target_temp

    @property
    def extra_state_attributes(self) -> dict:
        timer: dict[str, list] = {}
        for day in DAYS:
            slots = []
            for suffix in SLOT_SUFFIXES:
                f = self.hass.states.get(f"sensor.{self._ep}_ebusd_700_hwctimer_{day.lower()}_from{suffix}")
                t = self.hass.states.get(f"sensor.{self._ep}_ebusd_700_hwctimer_{day.lower()}_to{suffix}")
                if (
                    f and f.state not in ("unknown", "unavailable", _EMPTY)
                    and t and t.state not in ("unknown", "unavailable", _EMPTY)
                ):
                    slots.append({"from": f.state, "to": t.state})
            timer[day] = slots
        return {"time_program": timer}

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await mqtt.async_publish(
            self.hass,
            f"{self._mp}/700/HwcOpMode/set",
            json.dumps({"value": operation_mode}),
        )

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get("temperature")
        if temp is not None:
            await mqtt.async_publish(
                self.hass,
                f"{self._mp}/700/HwcTempDesired/set",
                json.dumps({"value": float(temp)}),
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
            f"{self._mp}/700/HwcTempDesired/set",
            json.dumps({"value": 70}),
        )
