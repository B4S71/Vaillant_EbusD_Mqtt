from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CURRENT_FLOW_TEMP,
    ATTR_CURRENT_HWC_STORAGE_TEMP,
    ATTR_CURRENT_OUTDOOR_TEMP,
    ATTR_CURRENT_ROOM_TEMP,
    ATTR_ENERGY_SUM,
    ATTR_FLOW_TEMP_DESIRED,
    ATTR_HC_MODE,
    ATTR_HWC_FLOW_TEMP_DESIRED,
    ATTR_HWC_TEMP_DESIRED,
    ATTR_VWZ_ELECTRIC_ENERGY,
    ATTR_VWZ_ENVIRONMENT_ENERGY,
    DOMAIN,
)
from .coordinator import VaillantEbusdCoordinator
from .entity import VaillantEbusdEntity


@dataclass(frozen=True, kw_only=True)
class VaillantSensorDescription(SensorEntityDescription):
    coordinator_attr: str


_TEMP_PARAMS = dict(
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
)

_ENERGY_PARAMS = dict(
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
)

SENSOR_DESCRIPTIONS: tuple[VaillantSensorDescription, ...] = (
    VaillantSensorDescription(
        key=ATTR_FLOW_TEMP_DESIRED,
        name="Vorlauf-Solltemperatur",
        coordinator_attr=ATTR_FLOW_TEMP_DESIRED,
        **_TEMP_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_HWC_TEMP_DESIRED,
        name="Warmwasser-Solltemperatur",
        coordinator_attr=ATTR_HWC_TEMP_DESIRED,
        **_TEMP_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_HWC_FLOW_TEMP_DESIRED,
        name="Warmwasser-Vorlauf-Solltemperatur",
        coordinator_attr=ATTR_HWC_FLOW_TEMP_DESIRED,
        **_TEMP_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_HC_MODE,
        name="Heizkreis-Modus",
        coordinator_attr=ATTR_HC_MODE,
    ),
    VaillantSensorDescription(
        key=ATTR_ENERGY_SUM,
        name="Wärmepumpe Energiesumme",
        coordinator_attr=ATTR_ENERGY_SUM,
        **_ENERGY_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_CURRENT_FLOW_TEMP,
        name="Vorlauftemperatur",
        coordinator_attr=ATTR_CURRENT_FLOW_TEMP,
        **_TEMP_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_CURRENT_ROOM_TEMP,
        name="Raumtemperatur",
        coordinator_attr=ATTR_CURRENT_ROOM_TEMP,
        **_TEMP_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_CURRENT_HWC_STORAGE_TEMP,
        name="Warmwasserspeicher-Temperatur",
        coordinator_attr=ATTR_CURRENT_HWC_STORAGE_TEMP,
        **_TEMP_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_CURRENT_OUTDOOR_TEMP,
        name="Außentemperatur",
        coordinator_attr=ATTR_CURRENT_OUTDOOR_TEMP,
        **_TEMP_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_VWZ_ELECTRIC_ENERGY,
        name="Stromverbrauch gesamt",
        coordinator_attr=ATTR_VWZ_ELECTRIC_ENERGY,
        **_ENERGY_PARAMS,
    ),
    VaillantSensorDescription(
        key=ATTR_VWZ_ENVIRONMENT_ENERGY,
        name="Umgebungswärme gesamt",
        coordinator_attr=ATTR_VWZ_ENVIRONMENT_ENERGY,
        **_ENERGY_PARAMS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: VaillantEbusdCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [VaillantSensor(coordinator, config_entry, desc) for desc in SENSOR_DESCRIPTIONS]
    )


class VaillantSensor(VaillantEbusdEntity, SensorEntity):
    """A sensor entity that reads a single value from the coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VaillantEbusdCoordinator,
        config_entry: ConfigEntry,
        description: VaillantSensorDescription,
    ) -> None:
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"

    @property
    def native_value(self):
        return getattr(self._coordinator, self.entity_description.coordinator_attr, None)
