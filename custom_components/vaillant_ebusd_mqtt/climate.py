"""Combined heating/cooling climate entity over the coordinator state."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COOLING_MAX_TEMP,
    DAYS,
    DEVICE_HEATING,
    DOMAIN,
    HEATING_MIN_TEMP,
    T_HC1_FLOW_TEMP,
    T_HC1_PUMP_STATUS,
    T_HEATING_TIMER,
    T_OUTSIDE_TEMP,
    T_ROOM_HUMIDITY,
    T_Z1_COOLING_TEMP,
    T_Z1_DAY_TEMP,
    T_Z1_OPMODE,
    T_Z1_OPMODE_COOLING,
    T_Z1_ROOM_TEMP,
    TEMP_STEP,
)
from .coordinator import VaillantCoordinator, VaillantEntity
from .timeprog import payload_from_slots, slots_from_day


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VaillantCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([VaillantHeatingClimate(coordinator)])

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


class VaillantHeatingClimate(VaillantEntity, ClimateEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = ["none", "comfort", "sleep"]
    _attr_min_temp = HEATING_MIN_TEMP
    _attr_max_temp = COOLING_MAX_TEMP
    _attr_target_temperature_step = TEMP_STEP

    def __init__(self, coordinator: VaillantCoordinator) -> None:
        super().__init__(coordinator, DEVICE_HEATING)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_heating"

    @property
    def hvac_mode(self) -> HVACMode:
        heat = self.coordinator.get_str(T_Z1_OPMODE)
        cool = self.coordinator.get_str(T_Z1_OPMODE_COOLING)
        heat_off = heat in (None, "off")
        cool_off = cool in (None, "off")
        if heat_off and cool_off:
            return HVACMode.OFF
        if cool_off:
            return HVACMode.HEAT
        if heat_off:
            return HVACMode.COOL
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        # hmu/State's enum mixes case: "ready"/"error"/"heating_water" are
        # lowercase but "Heating"/"Cooling" are capitalized.
        state = (self.coordinator.hmu_state or "").lower()
        if state == "heating":
            return HVACAction.HEATING
        if state == "cooling":
            return HVACAction.COOLING
        if state in ("ready", "heating_water", "error"):
            return HVACAction.IDLE
        return self._hvac_action_fallback()

    def _hvac_action_fallback(self) -> HVACAction:
        """Heuristic used while hmu/State hasn't reported a usable value yet.

        Mirrors a hand-built HA automation the user already relied on: pump
        duty decides idle-vs-running, the active op mode decides heat-vs-cool
        when only one circuit is on, and flow-vs-room temperature breaks the
        tie when both (or neither) op mode is conclusive.
        """
        pump = self.coordinator.get_float(T_HC1_PUMP_STATUS)
        if not pump:
            return HVACAction.IDLE
        heat = self.coordinator.get_str(T_Z1_OPMODE)
        cool = self.coordinator.get_str(T_Z1_OPMODE_COOLING)
        if cool not in (None, "off") and heat in (None, "off"):
            return HVACAction.COOLING
        if heat not in (None, "off") and cool in (None, "off"):
            return HVACAction.HEATING
        flow = self.coordinator.get_float(T_HC1_FLOW_TEMP)
        room = self.coordinator.get_float(T_Z1_ROOM_TEMP)
        if flow is not None and room is not None:
            if flow < room - 0.5:
                return HVACAction.COOLING
            if flow > room + 0.5:
                return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.get_float(T_Z1_ROOM_TEMP)

    @property
    def target_temperature_high(self) -> float | None:
        return self.coordinator.get_float(T_Z1_COOLING_TEMP)

    @property
    def target_temperature_low(self) -> float | None:
        return self.coordinator.get_float(T_Z1_DAY_TEMP)

    @property
    def preset_mode(self) -> str:
        if self.hvac_mode == HVACMode.COOL:
            return "comfort" if self.coordinator.get_str(T_Z1_OPMODE_COOLING) == "day" else "none"
        mode = self.coordinator.get_str(T_Z1_OPMODE)
        if mode == "day":
            return "comfort"
        if mode == "night":
            return "sleep"
        return "none"

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        humidity = self.coordinator.get_float(T_ROOM_HUMIDITY)
        if humidity is not None:
            attrs["current_humidity"] = humidity
        outside = self.coordinator.get_float(T_OUTSIDE_TEMP)
        if outside is not None:
            attrs["outside_temperature"] = outside
        attrs["time_program"] = {
            day: [
                {"from": s[0], "to": s[1]}
                for s in slots_from_day(
                    self.coordinator.get_timer_day(T_HEATING_TIMER, day)
                )
            ]
            for day in DAYS
        }
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        heat_val, cool_val = {
            HVACMode.OFF: ("off", "off"),
            HVACMode.HEAT: ("auto", "off"),
            HVACMode.COOL: ("off", "auto"),
            HVACMode.AUTO: ("auto", "auto"),
        }.get(hvac_mode, ("auto", "auto"))
        await self.coordinator.async_publish_scalar(T_Z1_OPMODE, heat_val)
        await self.coordinator.async_publish_scalar(T_Z1_OPMODE_COOLING, cool_val)

    async def async_set_temperature(self, **kwargs) -> None:
        if (high := kwargs.get("target_temp_high")) is not None:
            await self.coordinator.async_publish_scalar(T_Z1_COOLING_TEMP, float(high))
        if (low := kwargs.get("target_temp_low")) is not None:
            await self.coordinator.async_publish_scalar(T_Z1_DAY_TEMP, float(low))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if self.hvac_mode == HVACMode.COOL:
            val = "day" if preset_mode == "comfort" else "auto"
            await self.coordinator.async_publish_scalar(T_Z1_OPMODE_COOLING, val)
            return
        val = {"comfort": "day", "sleep": "night"}.get(preset_mode, "auto")
        await self.coordinator.async_publish_scalar(T_Z1_OPMODE, val)

    async def async_set_time_program(self, day: str, slots: list[dict]) -> None:
        payload = payload_from_slots([(s["from"], s["to"]) for s in slots])
        await self.coordinator.async_publish_timer(T_HEATING_TIMER, day, payload)
