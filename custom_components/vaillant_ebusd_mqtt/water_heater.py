from __future__ import annotations

import voluptuous as vol

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HOT_WATER_NAME,
    DAYS,
    DEFAULT_HOT_WATER_NAME,
    DOMAIN,
)
from .coordinator import VaillantEbusdCoordinator
from .entity import VaillantEbusdEntity

OPERATION_ECO = "eco"
OPERATION_PERFORMANCE = "performance"
OPERATION_OFF = "off"

_MODE_TO_EBUSD = {
    OPERATION_ECO: "auto",
    OPERATION_PERFORMANCE: "day",
    OPERATION_OFF: "off",
}
_EBUSD_TO_MODE = {v: k for k, v in _MODE_TO_EBUSD.items()}

SERVICE_SET_TIME_PROGRAM = "set_hot_water_time_program"
SERVICE_LEGIONELLA = "trigger_legionella_protection"

SET_TIME_PROGRAM_SCHEMA = {
    vol.Required("day"): vol.In(DAYS),
    vol.Required("slots"): vol.All(
        cv.ensure_list,
        [vol.Schema({vol.Required("from"): str, vol.Required("to"): str})],
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
    platform.async_register_entity_service(
        SERVICE_LEGIONELLA,
        {},
        "async_trigger_legionella_protection",
    )


class VaillantHotWater(VaillantEbusdEntity, WaterHeaterEntity):
    """Water heater entity for the Vaillant domestic hot water circuit."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = [OPERATION_ECO, OPERATION_PERFORMANCE, OPERATION_OFF]
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_min_temp = 40.0
    _attr_max_temp = 70.0

    def __init__(
        self, coordinator: VaillantEbusdCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, config_entry)
        self._attr_name = config_entry.data.get(
            CONF_HOT_WATER_NAME, DEFAULT_HOT_WATER_NAME
        )
        self._attr_unique_id = f"{config_entry.entry_id}_hot_water"

    # ------------------------------------------------------------------
    # State properties
    # ------------------------------------------------------------------

    @property
    def current_operation(self) -> str:
        if self._coordinator.disable_hwc_load:
            return OPERATION_OFF
        return _EBUSD_TO_MODE.get(self._coordinator.hc_mode or "auto", OPERATION_ECO)

    @property
    def target_temperature(self) -> float | None:
        return self._coordinator.hwc_temp_desired

    @property
    def extra_state_attributes(self) -> dict:
        return {"time_program": self._coordinator.hwc_timer}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self._coordinator.async_set_hc_mode(
            _MODE_TO_EBUSD.get(operation_mode, "auto")
        )

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get("temperature")
        if temp is not None:
            await self._coordinator.async_set_hwc_temp_desired(float(temp))

    async def async_set_time_program(self, day: str, slots: list[dict]) -> None:
        """Write a day's hot water time program to ebusd via MQTT.

        Example:
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

    async def async_trigger_legionella_protection(self) -> None:
        """Trigger a one-time legionella protection cycle (target → 70 °C).

        Example:
          action: vaillant_ebusd_mqtt.trigger_legionella_protection
          target:
            entity_id: water_heater.vaillant_warmwasser
        """
        await self._coordinator.async_trigger_legionella_protection()
