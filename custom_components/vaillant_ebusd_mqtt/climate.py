from __future__ import annotations

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_HEATING_NAME,
    DAYS,
    DEFAULT_HEATING_NAME,
    DOMAIN,
    EBUSD_MODE_AUTO,
    EBUSD_MODE_DAY,
    EBUSD_MODE_NIGHT,
    EBUSD_MODE_OFF,
)
from .coordinator import VaillantEbusdCoordinator

_HVAC_TO_EBUSD: dict[HVACMode, str] = {
    HVACMode.AUTO: EBUSD_MODE_AUTO,
    HVACMode.HEAT: EBUSD_MODE_DAY,
    HVACMode.COOL: EBUSD_MODE_NIGHT,
    HVACMode.OFF: EBUSD_MODE_OFF,
}
_EBUSD_TO_HVAC: dict[str, HVACMode] = {v: k for k, v in _HVAC_TO_EBUSD.items()}

SERVICE_SET_TIME_PROGRAM = "set_heating_time_program"

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
    async_add_entities([VaillantHeatingClimate(coordinator, config_entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_TIME_PROGRAM,
        SET_TIME_PROGRAM_SCHEMA,
        "async_set_time_program",
    )


class VaillantHeatingClimate(ClimateEntity):
    """Climate entity representing the Vaillant heating circuit."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_should_poll = False

    def __init__(
        self, coordinator: VaillantEbusdCoordinator, config_entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_name = config_entry.data.get(CONF_HEATING_NAME, DEFAULT_HEATING_NAME)
        self._attr_unique_id = f"{config_entry.entry_id}_heating"
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
    def hvac_mode(self) -> HVACMode:
        if self._coordinator.disable_hc:
            return HVACMode.OFF
        return _EBUSD_TO_HVAC.get(self._coordinator.hc_mode or EBUSD_MODE_AUTO, HVACMode.AUTO)

    @property
    def target_temperature(self) -> float | None:
        return self._coordinator.flow_temp_desired

    @property
    def extra_state_attributes(self) -> dict:
        return {"time_program": self._coordinator.cc_timer}

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        ebusd_mode = _HVAC_TO_EBUSD.get(hvac_mode, EBUSD_MODE_AUTO)
        await self._coordinator.async_set_hc_mode(ebusd_mode)

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get("temperature")
        if temp is not None:
            from homeassistant.components import mqtt
            import json

            await mqtt.async_publish(
                self.hass,
                f"{self._coordinator._hmu_prefix}/SetMode/set",
                json.dumps({"flowtempdesired": temp}),
            )

    async def async_set_time_program(self, day: str, slots: list[dict]) -> None:
        """Set the heating time program for a specific day.

        Example service call:
          action: vaillant_ebusd_mqtt.set_heating_time_program
          target:
            entity_id: climate.vaillant_heizung
          data:
            day: Monday
            slots:
              - from: "06:00"
                to: "21:00"
        """
        await self._coordinator.async_set_cc_timer(day, slots)
