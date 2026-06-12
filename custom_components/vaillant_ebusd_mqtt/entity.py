from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .coordinator import VaillantEbusdCoordinator


class VaillantEbusdEntity(Entity):
    """Base class for all Vaillant eBusd entities."""

    _attr_should_poll = False

    def __init__(
        self, coordinator: VaillantEbusdCoordinator, config_entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._config_entry = config_entry
        self._remove_listener: callback | None = None

    async def async_added_to_hass(self) -> None:
        self._remove_listener = self._coordinator.async_add_listener(
            self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener:
            self._remove_listener()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=self._config_entry.title,
            manufacturer="Vaillant",
            model="ebusd MQTT Bridge",
        )
