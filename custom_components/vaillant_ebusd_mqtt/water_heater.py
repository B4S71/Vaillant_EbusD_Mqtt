from __future__ import annotations

import json

import voluptuous as vol

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HOT_WATER_NAME,
    DAYS,
    DEFAULT_HOT_WATER_NAME,
    DOMAIN,
)
from .coordinator import VaillantEbusdCoordinator

OPERATION_ECO = "eco"
OPERATION_PERFORMANCE = "performance"
OPERATION_OFF = "off"

SERVICE_SET_TIME_PROGRAM = "set_hot_water_time_program"

SET_TIME_PROGRAM_SCHEMA = {
    vol.Required("day"): vol.In(DAYS),
    vol.Required("slots"): vol.All(
        cv.ensure_list,
        [
            vol.Schema(
                {
                    vol.Required("from"): str,
                    vol.Required("to"): str,
                }
            )
        ],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VaillantEbusdCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([VaillantHotWater(coordinator, config_entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_TIME_PROGRAM,
        SET_TIME_PROGRAM_SCHEMA,
        "async_set_time_program",
    )


class VaillantHotWater(WaterHeaterEntity):
    """Water heater entity representing the Vaillant domestic hot water circuit."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = [OPERATION_ECO, OPERATION_PERFORMANCE, OPERATION_OFF]
    _attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
    _attr_should_poll = False

    def __init__(
        self, coordinator: VaillantEbusdCoordinator, config_entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_name = config_entry.data.get(
            CONF_HOT_WATER_NAME, DEFAULT_HOT_WATER_NAME
        )
        self._attr_unique_id = f"{config_entry.entry_id}_hot_water"
        self._remove_listener: callback | None = None

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self._coordinator.async_add_listener(
            self._on_coordinator_update
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()

    @callback
    def _on_coordinator_update(self) -> None:
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # State properties
    # ------------------------------------------------------------------

    @property
    def current_operation(self) -> str:
        if self._coordinator.disable_hc:
            return OPERATION_OFF
        mode = self._coordinator.hc_mode or OPERATION_ECO
        return {
            "auto": OPERATION_ECO,
            "day": OPERATION_PERFORMANCE,
            "off": OPERATION_OFF,
        }.get(mode, OPERATION_ECO)

    @property
    def extra_state_attributes(self) -> dict:
        return {"time_program": self._coordinator.hwc_timer}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        ebusd_mode = {
            OPERATION_ECO: "auto",
            OPERATION_PERFORMANCE: "day",
            OPERATION_OFF: "off",
        }.get(operation_mode, "auto")
        await self._coordinator.async_set_hc_mode(ebusd_mode)

    async def async_set_time_program(self, day: str, slots: list[dict]) -> None:
        """Set the hot water time program for a specific day.

        Example service call:
          action: vaillant_ebusd_mqtt.set_hot_water_time_program
          target:
            entity_id: water_heater.vaillant_warmwasser
          data:
            day: Monday
            slots:
              - from: "06:30"
                to: "20:00"
        """
        await self._coordinator.async_set_hwc_timer(day, slots)
