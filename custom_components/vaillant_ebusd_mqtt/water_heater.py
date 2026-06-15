"""Combined hot water entity over the coordinator state."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DAYS,
    DEVICE_HOT_WATER,
    DOMAIN,
    HWC_MAX_TEMP,
    HWC_MIN_TEMP,
    T_HWC_OPMODE,
    T_HWC_STORAGE_TEMP,
    T_HWC_TEMP_DESIRED,
    T_HWC_TIMER,
)
from .coordinator import VaillantCoordinator, VaillantEntity
from .timeprog import payload_from_slots, slots_from_day

# The water_heater card only has icons for HA's built-in operation modes, so the
# Vaillant HwcOpMode (off/auto/day) is mapped onto standard modes here. The native
# off/auto/day wording is still available on the separate "Hot water mode" select.
_EBUSD_TO_OP = {"off": "off", "auto": "eco", "day": "performance", "night": "eco"}
_OP_TO_EBUSD = {"off": "off", "eco": "auto", "performance": "day"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VaillantCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([VaillantHotWater(coordinator)])

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


class VaillantHotWater(VaillantEntity, WaterHeaterEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = list(_OP_TO_EBUSD)
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_min_temp = HWC_MIN_TEMP
    _attr_max_temp = HWC_MAX_TEMP

    def __init__(self, coordinator: VaillantCoordinator) -> None:
        super().__init__(coordinator, DEVICE_HOT_WATER)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_hot_water"

    @property
    def current_operation(self) -> str | None:
        mode = self.coordinator.get_str(T_HWC_OPMODE)
        return _EBUSD_TO_OP.get(mode) if mode else None

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.get_float(T_HWC_STORAGE_TEMP)

    @property
    def target_temperature(self) -> float | None:
        value = self.coordinator.get_float(T_HWC_TEMP_DESIRED)
        return value if value and value > 0 else None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "time_program": {
                day: [
                    {"from": s[0], "to": s[1]}
                    for s in slots_from_day(
                        self.coordinator.get_timer_day(T_HWC_TIMER, day)
                    )
                ]
                for day in DAYS
            }
        }

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self.coordinator.async_publish_scalar(
            T_HWC_OPMODE, _OP_TO_EBUSD.get(operation_mode, "auto")
        )

    async def async_set_temperature(self, **kwargs) -> None:
        if (temp := kwargs.get("temperature")) is not None:
            await self.coordinator.async_publish_scalar(T_HWC_TEMP_DESIRED, float(temp))

    async def async_set_time_program(self, day: str, slots: list[dict]) -> None:
        payload = payload_from_slots([(s["from"], s["to"]) for s in slots])
        await self.coordinator.async_publish_timer(T_HWC_TIMER, day, payload)

    async def async_trigger_legionella_protection(self) -> None:
        await self.coordinator.async_publish_scalar(T_HWC_TEMP_DESIRED, HWC_MAX_TEMP)
