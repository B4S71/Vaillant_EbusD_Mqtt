from __future__ import annotations

import json

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENTITY_PREFIX, CONF_MQTT_PREFIX, DEFAULT_ENTITY_PREFIX, DAYS, DOMAIN, SLOT_SUFFIXES

_HVAC_TO_EBUSD: dict[HVACMode, str] = {
    HVACMode.OFF: "off",
    HVACMode.AUTO: "auto",
    HVACMode.HEAT: "day",
    HVACMode.COOL: "night",
}
_EBUSD_TO_HVAC: dict[str, HVACMode] = {v: k for k, v in _HVAC_TO_EBUSD.items()}
_EMPTY = "-:-"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([VaillantHeatingClimate(config_entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_heating_time_program",
        {
            vol.Required("day"): vol.In(DAYS),
            vol.Required("slots"): vol.All(
                cv.ensure_list,
                [vol.Schema({vol.Required("from"): str, vol.Required("to"): str})],
            ),
        },
        "async_set_time_program",
    )


class VaillantHeatingClimate(ClimateEntity):
    _attr_should_poll = False
    _attr_name = "Vaillant Heizung"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = ["none", "comfort", "sleep"]
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._mp = config_entry.data[CONF_MQTT_PREFIX]
        self._ep = config_entry.data.get(CONF_ENTITY_PREFIX, DEFAULT_ENTITY_PREFIX)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_heating"

        self._hvac_mode_raw: str | None = None
        self._temp_high: float | None = None
        self._temp_low: float | None = None
        self._current_temp: float | None = None
        self._humidity: float | None = None
        self._outside_temp: float | None = None
        self._preset_raw: str | None = None

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
            (f"{base}/Z1OpMode",             self._on_mode),
            (f"{base}/Z1DayTemp",            self._on_day_temp),
            (f"{base}/Z1NightTemp",          self._on_night_temp),
            (f"{base}/Z1RoomTemp",           self._on_current_temp),
            (f"{base}/RoomHumidity",         self._on_humidity),
            (f"{base}/DisplayedOutsideTemp", self._on_outside_temp),
            (f"{base}/Z1SfMode",             self._on_preset),
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
    def _on_mode(self, msg) -> None:
        v = self._val(msg)
        if v is not None:
            self._hvac_mode_raw = str(v)
        self.async_write_ha_state()

    @callback
    def _on_day_temp(self, msg) -> None:
        v = self._float_val(msg)
        if v is not None:
            self._temp_high = v
        self.async_write_ha_state()

    @callback
    def _on_night_temp(self, msg) -> None:
        v = self._float_val(msg)
        if v is not None:
            self._temp_low = v
        self.async_write_ha_state()

    @callback
    def _on_current_temp(self, msg) -> None:
        v = self._float_val(msg)
        if v is not None:
            self._current_temp = v
        self.async_write_ha_state()

    @callback
    def _on_humidity(self, msg) -> None:
        v = self._float_val(msg)
        if v is not None:
            self._humidity = v
        self.async_write_ha_state()

    @callback
    def _on_outside_temp(self, msg) -> None:
        v = self._float_val(msg)
        if v is not None:
            self._outside_temp = v
        self.async_write_ha_state()

    @callback
    def _on_preset(self, msg) -> None:
        v = self._val(msg)
        if v is not None:
            self._preset_raw = str(v)
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> HVACMode:
        return _EBUSD_TO_HVAC.get(self._hvac_mode_raw or "", HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction:
        if self._hvac_mode_raw in (None, "off"):
            return HVACAction.OFF
        cur = self._current_temp
        if self._hvac_mode_raw == "night":
            if cur is not None and self._temp_low is not None:
                return HVACAction.HEATING if cur < self._temp_low - 0.3 else HVACAction.IDLE
        else:  # auto / day
            if cur is not None and self._temp_high is not None:
                return HVACAction.HEATING if cur < self._temp_high - 0.3 else HVACAction.IDLE
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        return self._current_temp

    @property
    def target_temperature_high(self) -> float | None:
        return self._temp_high

    @property
    def target_temperature_low(self) -> float | None:
        return self._temp_low

    @property
    def preset_mode(self) -> str:
        return self._preset_raw if self._preset_raw in (self._attr_preset_modes or []) else "none"

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        if self._humidity is not None:
            attrs["current_humidity"] = self._humidity
        if self._outside_temp is not None:
            attrs["outside_temperature"] = self._outside_temp
        timer: dict[str, list] = {}
        for day in DAYS:
            slots = []
            for suffix in SLOT_SUFFIXES:
                f = self.hass.states.get(f"sensor.{self._ep}_ebusd_700_cctimer_{day.lower()}_from{suffix}")
                t = self.hass.states.get(f"sensor.{self._ep}_ebusd_700_cctimer_{day.lower()}_to{suffix}")
                if (
                    f and f.state not in ("unknown", "unavailable", _EMPTY)
                    and t and t.state not in ("unknown", "unavailable", _EMPTY)
                ):
                    slots.append({"from": f.state, "to": t.state})
            timer[day] = slots
        attrs["time_program"] = timer
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await mqtt.async_publish(
            self.hass,
            f"{self._mp}/700/Z1OpMode/set",
            json.dumps({"value": _HVAC_TO_EBUSD.get(hvac_mode, "auto")}),
        )

    async def async_set_temperature(self, **kwargs) -> None:
        if (high := kwargs.get("target_temp_high")) is not None:
            await mqtt.async_publish(
                self.hass,
                f"{self._mp}/700/Z1DayTemp/set",
                json.dumps({"value": float(high)}),
            )
        if (low := kwargs.get("target_temp_low")) is not None:
            await mqtt.async_publish(
                self.hass,
                f"{self._mp}/700/Z1NightTemp/set",
                json.dumps({"value": float(low)}),
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await mqtt.async_publish(
            self.hass,
            f"{self._mp}/700/Z1SfMode/set",
            json.dumps({"value": preset_mode}),
        )

    async def async_set_time_program(self, day: str, slots: list[dict]) -> None:
        payload: dict = {}
        for i, suffix in enumerate(SLOT_SUFFIXES):
            payload[f"from{suffix}"] = slots[i]["from"] if i < len(slots) else _EMPTY
            payload[f"to{suffix}"] = slots[i]["to"] if i < len(slots) else _EMPTY
        await mqtt.async_publish(
            self.hass, f"{self._mp}/700/CcTimer_{day}/set", json.dumps(payload)
        )
