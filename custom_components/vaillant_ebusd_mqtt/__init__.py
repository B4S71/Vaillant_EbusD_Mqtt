from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import VaillantCoordinator

PLATFORMS = ["climate", "water_heater", "select", "number", "calendar"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = VaillantCoordinator(hass, entry)
    await coordinator.async_setup()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: VaillantCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.async_unload()
    return unloaded
