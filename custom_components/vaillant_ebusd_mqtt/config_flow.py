from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_FLOW_TEMP_TOPIC,
    CONF_HEATING_NAME,
    CONF_HMU_PREFIX,
    CONF_HOT_WATER_NAME,
    CONF_MQTT_PREFIX,
    CONF_OUTDOOR_TEMP_TOPIC,
    CONF_ROOM_TEMP_TOPIC,
    DEFAULT_HEATING_NAME,
    DEFAULT_HMU_PREFIX,
    DEFAULT_HOT_WATER_NAME,
    DEFAULT_MQTT_PREFIX,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MQTT_PREFIX, default=DEFAULT_MQTT_PREFIX): str,
        vol.Required(CONF_HMU_PREFIX, default=DEFAULT_HMU_PREFIX): str,
        vol.Optional(CONF_HEATING_NAME, default=DEFAULT_HEATING_NAME): str,
        vol.Optional(CONF_HOT_WATER_NAME, default=DEFAULT_HOT_WATER_NAME): str,
        # Optional measured-temperature topics — leave blank to disable
        vol.Optional(CONF_FLOW_TEMP_TOPIC, default=""): str,
        vol.Optional(CONF_ROOM_TEMP_TOPIC, default=""): str,
        vol.Optional(CONF_OUTDOOR_TEMP_TOPIC, default=""): str,
    }
)


class VaillantEbusdConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Vaillant eBusd MQTT integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_MQTT_PREFIX])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_HEATING_NAME, DEFAULT_HEATING_NAME),
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)
