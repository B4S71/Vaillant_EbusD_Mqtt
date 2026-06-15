"""Temperature setpoint numbers mirroring the Vaillant app."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COOLING_MAX_TEMP,
    COOLING_MIN_TEMP,
    DEVICE_HEATING,
    DEVICE_HOT_WATER,
    DOMAIN,
    HEATING_MAX_TEMP,
    HEATING_MIN_TEMP,
    HWC_MAX_TEMP,
    HWC_MIN_TEMP,
    T_HWC_TEMP_DESIRED,
    T_Z1_COOLING_TEMP,
    T_Z1_DAY_TEMP,
    T_Z1_NIGHT_TEMP,
    TEMP_STEP,
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
            VaillantTempNumber(
                coordinator, DEVICE_HEATING, "heating_day_temp",
                "Heating day temperature", T_Z1_DAY_TEMP,
                HEATING_MIN_TEMP, HEATING_MAX_TEMP,
            ),
            VaillantTempNumber(
                coordinator, DEVICE_HEATING, "heating_night_temp",
                "Heating night temperature", T_Z1_NIGHT_TEMP,
                HEATING_MIN_TEMP, HEATING_MAX_TEMP,
            ),
            VaillantTempNumber(
                coordinator, DEVICE_HEATING, "cooling_temp",
                "Cooling temperature", T_Z1_COOLING_TEMP,
                COOLING_MIN_TEMP, COOLING_MAX_TEMP,
            ),
            VaillantTempNumber(
                coordinator, DEVICE_HOT_WATER, "hot_water_temp",
                "Hot water temperature", T_HWC_TEMP_DESIRED,
                HWC_MIN_TEMP, HWC_MAX_TEMP,
            ),
        ]
    )


class VaillantTempNumber(VaillantEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = TEMP_STEP

    def __init__(
        self,
        coordinator: VaillantCoordinator,
        device: str,
        key: str,
        name: str,
        topic: str,
        min_temp: float,
        max_temp: float,
    ) -> None:
        super().__init__(coordinator, device)
        self._topic = topic
        self._attr_name = name
        self._attr_native_min_value = min_temp
        self._attr_native_max_value = max_temp
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.get_float(self._topic)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_publish_scalar(self._topic, float(value))
