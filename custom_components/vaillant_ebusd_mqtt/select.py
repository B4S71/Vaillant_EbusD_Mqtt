"""Betriebsart (operating mode) selects mirroring the Vaillant app."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COOLING_MODES,
    DEVICE_HEATING,
    DEVICE_HOT_WATER,
    DOMAIN,
    HEATING_MODES,
    HOT_WATER_MODES,
    T_HWC_OPMODE,
    T_Z1_OPMODE,
    T_Z1_OPMODE_COOLING,
)
from .coordinator import VaillantCoordinator, VaillantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VaillantCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            VaillantModeSelect(
                coordinator, DEVICE_HEATING, "heating_mode",
                "Heating mode", T_Z1_OPMODE, HEATING_MODES,
            ),
            VaillantModeSelect(
                coordinator, DEVICE_HEATING, "cooling_mode",
                "Cooling mode", T_Z1_OPMODE_COOLING, COOLING_MODES,
            ),
            VaillantModeSelect(
                coordinator, DEVICE_HOT_WATER, "hot_water_mode",
                "Hot water mode", T_HWC_OPMODE, HOT_WATER_MODES,
            ),
        ]
    )


class VaillantModeSelect(VaillantEntity, SelectEntity):
    def __init__(
        self,
        coordinator: VaillantCoordinator,
        device: str,
        key: str,
        name: str,
        topic: str,
        options: list[str],
    ) -> None:
        super().__init__(coordinator, device)
        self._topic = topic
        self._attr_name = name
        self._attr_options = options
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.get_str(self._topic)
        return value if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_publish_scalar(self._topic, option)
