from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CIR_PUMP_ACTIVE,
    ATTR_DISABLE_HC,
    ATTR_DISABLE_HWC_LOAD,
    ATTR_DISABLE_HWC_TAPPING,
    ATTR_HC_MODE_ACTIVE,
    ATTR_HMU_ON,
    ATTR_HWC_MODE_ACTIVE,
    DOMAIN,
)
from .coordinator import VaillantEbusdCoordinator
from .entity import VaillantEbusdEntity


@dataclass(frozen=True, kw_only=True)
class VaillantBinaryDescription(BinarySensorEntityDescription):
    coordinator_attr: str


BINARY_DESCRIPTIONS: tuple[VaillantBinaryDescription, ...] = (
    VaillantBinaryDescription(
        key=ATTR_HMU_ON,
        translation_key=ATTR_HMU_ON,
        coordinator_attr=ATTR_HMU_ON,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    VaillantBinaryDescription(
        key=ATTR_CIR_PUMP_ACTIVE,
        translation_key=ATTR_CIR_PUMP_ACTIVE,
        coordinator_attr=ATTR_CIR_PUMP_ACTIVE,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    VaillantBinaryDescription(
        key=ATTR_HC_MODE_ACTIVE,
        translation_key=ATTR_HC_MODE_ACTIVE,
        coordinator_attr=ATTR_HC_MODE_ACTIVE,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    VaillantBinaryDescription(
        key=ATTR_HWC_MODE_ACTIVE,
        translation_key=ATTR_HWC_MODE_ACTIVE,
        coordinator_attr=ATTR_HWC_MODE_ACTIVE,
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    VaillantBinaryDescription(
        key=ATTR_DISABLE_HC,
        translation_key=ATTR_DISABLE_HC,
        coordinator_attr=ATTR_DISABLE_HC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    VaillantBinaryDescription(
        key=ATTR_DISABLE_HWC_LOAD,
        translation_key=ATTR_DISABLE_HWC_LOAD,
        coordinator_attr=ATTR_DISABLE_HWC_LOAD,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    VaillantBinaryDescription(
        key=ATTR_DISABLE_HWC_TAPPING,
        translation_key=ATTR_DISABLE_HWC_TAPPING,
        coordinator_attr=ATTR_DISABLE_HWC_TAPPING,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VaillantEbusdCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            VaillantBinarySensor(coordinator, config_entry, desc)
            for desc in BINARY_DESCRIPTIONS
        ]
    )


class VaillantBinarySensor(VaillantEbusdEntity, BinarySensorEntity):
    """A binary sensor that reads a boolean value from the coordinator."""

    def __init__(
        self,
        coordinator: VaillantEbusdCoordinator,
        config_entry: ConfigEntry,
        description: VaillantBinaryDescription,
    ) -> None:
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        val = getattr(self._coordinator, self.entity_description.coordinator_attr, None)
        if isinstance(val, bool):
            return val
        return None
