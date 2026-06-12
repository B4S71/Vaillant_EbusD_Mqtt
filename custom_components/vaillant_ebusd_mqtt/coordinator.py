from __future__ import annotations

import json
import logging
from collections.abc import Callable

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_CIR_PUMP_ACTIVE,
    ATTR_CURRENT_FLOW_TEMP,
    ATTR_CURRENT_HWC_STORAGE_TEMP,
    ATTR_CURRENT_OUTDOOR_TEMP,
    ATTR_CURRENT_ROOM_TEMP,
    ATTR_DISABLE_HC,
    ATTR_DISABLE_HWC_LOAD,
    ATTR_DISABLE_HWC_TAPPING,
    ATTR_ENERGY_SUM,
    ATTR_FLOW_TEMP_DESIRED,
    ATTR_HC_MODE,
    ATTR_HC_MODE_ACTIVE,
    ATTR_HMU_ON,
    ATTR_HWC_FLOW_TEMP_DESIRED,
    ATTR_HWC_MODE_ACTIVE,
    ATTR_HWC_TEMP_DESIRED,
    CONF_FLOW_TEMP_TOPIC,
    CONF_HMU_PREFIX,
    CONF_HWC_STORAGE_TEMP_TOPIC,
    CONF_MQTT_PREFIX,
    CONF_OUTDOOR_TEMP_TOPIC,
    CONF_ROOM_TEMP_TOPIC,
    DAYS,
    SLOT_SUFFIXES,
)

_LOGGER = logging.getLogger(__name__)
_EMPTY = "-:-"


def _parse_bool(data: dict) -> bool | None:
    """Parse an on/off value from an ebusd JSON payload dict."""
    for field in ("onoff", "value", "status"):
        val = data.get(field)
        if val is not None:
            return str(val).lower() in ("on", "1", "true", "yes")
    return None


def _parse_float(data: dict) -> float | None:
    """Parse a numeric value from an ebusd JSON payload dict."""
    for field in ("value", "temp", "temperature"):
        val = data.get(field)
        if val is not None:
            try:
                result = float(val)
                return result if result != 0 else None
            except (ValueError, TypeError):
                return None
    return None


class VaillantEbusdCoordinator:
    """Manages all MQTT subscriptions and shared state for one ebusd device."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self._hass = hass
        self._config_entry = config_entry
        self._mqtt_prefix: str = config_entry.data[CONF_MQTT_PREFIX]
        self._hmu_prefix: str = config_entry.data[CONF_HMU_PREFIX]
        self._flow_temp_topic: str = config_entry.data.get(CONF_FLOW_TEMP_TOPIC, "")
        self._room_temp_topic: str = config_entry.data.get(CONF_ROOM_TEMP_TOPIC, "")
        self._outdoor_temp_topic: str = config_entry.data.get(CONF_OUTDOOR_TEMP_TOPIC, "")
        # Auto-derive HwcStorageTemp topic from mqtt_prefix if not overridden
        hwc_storage_override = config_entry.data.get(CONF_HWC_STORAGE_TEMP_TOPIC, "")
        self._hwc_storage_temp_topic: str = (
            hwc_storage_override if hwc_storage_override else f"{self._mqtt_prefix}/HwcStorageTemp"
        )

        # Time programs: day → list[{"from": "HH:MM", "to": "HH:MM"}]
        self.cc_timer: dict[str, list[dict]] = {}
        self.hwc_timer: dict[str, list[dict]] = {}

        # SetMode fields
        self.hc_mode: str | None = None
        self.disable_hc: bool = False
        self.disable_hwc_load: bool = False
        self.disable_hwc_tapping: bool = False
        self.flow_temp_desired: float | None = None
        self.hwc_temp_desired: float | None = None
        self.hwc_flow_temp_desired: float | None = None

        # Status from individual topics
        self.hmu_on: bool | None = None
        self.cir_pump_active: bool | None = None
        self.hc_mode_active: bool | None = None
        self.hwc_mode_active: bool | None = None  # "Warmwasser bereitet auf"
        self.energy_sum: float | None = None

        # Optional measured temperatures
        self.current_flow_temp: float | None = None
        self.current_room_temp: float | None = None
        self.current_outdoor_temp: float | None = None
        self.current_hwc_storage_temp: float | None = None

        self._listeners: list[Callable] = []
        self._unsubscribe: list[Callable] = []

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Subscribe to all MQTT topics."""
        for day in DAYS:
            self._unsubscribe.append(
                await mqtt.async_subscribe(
                    self._hass,
                    f"{self._mqtt_prefix}/CcTimer_{day}",
                    lambda msg, d=day: self._on_timer(self.cc_timer, d, msg),
                    encoding="utf-8",
                )
            )
            self._unsubscribe.append(
                await mqtt.async_subscribe(
                    self._hass,
                    f"{self._mqtt_prefix}/HwcTimer_{day}",
                    lambda msg, d=day: self._on_timer(self.hwc_timer, d, msg),
                    encoding="utf-8",
                )
            )

        # SetMode (hcmode, temps, disable flags)
        self._unsubscribe.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._hmu_prefix}/SetMode",
                self._on_setmode,
                encoding="utf-8",
            )
        )

        # Individual status topics
        for topic, attr in (
            (f"{self._hmu_prefix}/StatusCirPump", ATTR_CIR_PUMP_ACTIVE),
            (f"{self._hmu_prefix}/HcModeActive", ATTR_HC_MODE_ACTIVE),
            (f"{self._hmu_prefix}/HwcModeActive", ATTR_HWC_MODE_ACTIVE),
        ):
            self._unsubscribe.append(
                await mqtt.async_subscribe(
                    self._hass,
                    topic,
                    lambda msg, a=attr: self._on_bool_topic(a, msg),
                    encoding="utf-8",
                )
            )

        # HMU on/off state
        self._unsubscribe.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._hmu_prefix}/State",
                self._on_hmu_state,
                encoding="utf-8",
            )
        )

        # Energy sum (always subscribed; shows None until first message)
        self._unsubscribe.append(
            await mqtt.async_subscribe(
                self._hass,
                f"{self._mqtt_prefix}/PrEnergySum",
                self._on_energy_sum,
                encoding="utf-8",
            )
        )

        # Optional measured temperature topics
        for topic, attr in (
            (self._flow_temp_topic, ATTR_CURRENT_FLOW_TEMP),
            (self._room_temp_topic, ATTR_CURRENT_ROOM_TEMP),
            (self._outdoor_temp_topic, ATTR_CURRENT_OUTDOOR_TEMP),
            (self._hwc_storage_temp_topic, ATTR_CURRENT_HWC_STORAGE_TEMP),
        ):
            if topic:
                self._unsubscribe.append(
                    await mqtt.async_subscribe(
                        self._hass,
                        topic,
                        lambda msg, a=attr: self._on_float_topic(a, msg),
                        encoding="utf-8",
                    )
                )

    async def async_unload(self) -> None:
        for unsub in self._unsubscribe:
            unsub()
        self._unsubscribe.clear()

    # ------------------------------------------------------------------
    # MQTT receive handlers
    # ------------------------------------------------------------------

    @callback
    def _on_timer(self, store: dict, day: str, msg) -> None:
        try:
            data = json.loads(msg.payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Bad JSON on timer topic for %s: %s", day, msg.payload)
            return
        slots = []
        for suffix in SLOT_SUFFIXES:
            from_val = data.get(f"from{suffix}", _EMPTY)
            to_val = data.get(f"to{suffix}", _EMPTY)
            if from_val and from_val != _EMPTY:
                slots.append({"from": from_val, "to": to_val})
        store[day] = slots
        self._notify()

    @callback
    def _on_setmode(self, msg) -> None:
        try:
            data = json.loads(msg.payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Bad JSON on SetMode: %s", msg.payload)
            return

        self.hc_mode = data.get("hcmode")
        self.disable_hc = str(data.get("disablehc", "0")) == "1"
        self.disable_hwc_load = str(data.get("disablehwcload", "0")) == "1"
        self.disable_hwc_tapping = str(data.get("disablehwctapping", "0")) == "1"

        for attr, key in (
            (ATTR_FLOW_TEMP_DESIRED, "flowtempdesired"),
            (ATTR_HWC_TEMP_DESIRED, "hwctempdesired"),
            (ATTR_HWC_FLOW_TEMP_DESIRED, "hwcflowtempdesired"),
        ):
            raw = data.get(key)
            if raw is not None:
                try:
                    val = float(raw)
                    setattr(self, attr, val if val != 0 else None)
                except (ValueError, TypeError):
                    setattr(self, attr, None)

        self._notify()

    @callback
    def _on_bool_topic(self, attr: str, msg) -> None:
        try:
            data = json.loads(msg.payload)
            setattr(self, attr, _parse_bool(data))
            self._notify()
        except json.JSONDecodeError:
            _LOGGER.warning("Bad JSON on %s: %s", attr, msg.payload)

    @callback
    def _on_hmu_state(self, msg) -> None:
        try:
            data = json.loads(msg.payload)
            self.hmu_on = _parse_bool(data)
            self._notify()
        except json.JSONDecodeError:
            _LOGGER.warning("Bad JSON on HMU State: %s", msg.payload)

    @callback
    def _on_energy_sum(self, msg) -> None:
        try:
            data = json.loads(msg.payload)
            self.energy_sum = _parse_float(data)
            self._notify()
        except json.JSONDecodeError:
            _LOGGER.warning("Bad JSON on PrEnergySum: %s", msg.payload)

    @callback
    def _on_float_topic(self, attr: str, msg) -> None:
        try:
            data = json.loads(msg.payload)
            setattr(self, attr, _parse_float(data))
            self._notify()
        except json.JSONDecodeError:
            _LOGGER.warning("Bad JSON on %s: %s", attr, msg.payload)

    # ------------------------------------------------------------------
    # MQTT publish helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_timer_payload(slots: list[dict]) -> str:
        payload: dict = {}
        for i, suffix in enumerate(SLOT_SUFFIXES):
            if i < len(slots):
                payload[f"from{suffix}"] = slots[i]["from"]
                payload[f"to{suffix}"] = slots[i]["to"]
            else:
                payload[f"from{suffix}"] = _EMPTY
                payload[f"to{suffix}"] = _EMPTY
        return json.dumps(payload)

    async def async_set_cc_timer(self, day: str, slots: list[dict]) -> None:
        await mqtt.async_publish(
            self._hass,
            f"{self._mqtt_prefix}/CcTimer_{day}/set",
            self._build_timer_payload(slots),
        )

    async def async_set_hwc_timer(self, day: str, slots: list[dict]) -> None:
        await mqtt.async_publish(
            self._hass,
            f"{self._mqtt_prefix}/HwcTimer_{day}/set",
            self._build_timer_payload(slots),
        )

    async def async_set_hc_mode(self, ebusd_mode: str) -> None:
        await mqtt.async_publish(
            self._hass,
            f"{self._hmu_prefix}/SetMode/set",
            json.dumps({"hcmode": ebusd_mode}),
        )

    async def async_set_flow_temp_desired(self, temp: float) -> None:
        await mqtt.async_publish(
            self._hass,
            f"{self._hmu_prefix}/SetMode/set",
            json.dumps({"flowtempdesired": temp}),
        )

    async def async_set_hwc_temp_desired(self, temp: float) -> None:
        await mqtt.async_publish(
            self._hass,
            f"{self._hmu_prefix}/SetMode/set",
            json.dumps({"hwctempdesired": temp}),
        )

    async def async_trigger_legionella_protection(self) -> None:
        """Set hot water target to 70 °C for a one-time legionella cycle."""
        await mqtt.async_publish(
            self._hass,
            f"{self._hmu_prefix}/SetMode/set",
            json.dumps({"hwctempdesired": 70}),
        )

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------

    @callback
    def async_add_listener(self, listener: Callable) -> Callable:
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in self._listeners:
            listener()
