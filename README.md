# Vaillant eBusd MQTT

Home Assistant custom integration for Vaillant heat pumps controlled via [ebusd](https://github.com/john30/ebusd) over MQTT.

Replaces manual `input_datetime` helpers + automations with proper `climate` and `water_heater` entities that read/write MQTT directly in the integration layer.

## Features

- **`climate` entity** — heating circuit with HVAC mode and weekly time program (CcTimer)
- **`water_heater` entity** — domestic hot water with operation mode and weekly time program (HwcTimer)
- **Local push** — subscribes directly to ebusd MQTT topics, no polling
- **Synchronisation in the integration layer** — no automations needed

## Requirements

- ebusd with MQTT enabled (see [ebusd MQTT docs](https://github.com/john30/ebusd/wiki/5.-MQTT))
- Home Assistant MQTT integration configured

## Installation (HACS)

### One-click (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=B4S71&repository=Vaillant_EbusD_Mqtt&category=integration)

### Manual via HACS

1. Open HACS in Home Assistant
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**
3. Add `https://github.com/B4S71/Vaillant_EbusD_Mqtt` with category **Integration**
4. Search for *Vaillant eBusd MQTT* and install it
5. Restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration** → search for *Vaillant eBusd MQTT*

## Configuration

| Field | Default | Description |
|-------|---------|-------------|
| MQTT prefix | `ebusd/700` | Topic prefix for CcTimer / HwcTimer (heating circuit address on the bus) |
| HMU prefix | `ebusd/hmu` | Topic prefix for SetMode (heat management unit) |
| Heating name | `Vaillant Heizung` | Friendly name for the climate entity |
| Hot water name | `Vaillant Warmwasser` | Friendly name for the water_heater entity |

## MQTT topic structure

The integration expects the standard ebusd MQTT format:

| Direction | Topic | Payload |
|-----------|-------|---------|
| Read | `ebusd/700/CcTimer_{Day}` | `{"from":"HH:MM","to":"HH:MM","from_2":"-:-","to_2":"-:-","from_3":"-:-","to_3":"-:-"}` |
| Write | `ebusd/700/CcTimer_{Day}/set` | same |
| Read | `ebusd/700/HwcTimer_{Day}` | same |
| Write | `ebusd/700/HwcTimer_{Day}/set` | same |
| Read | `ebusd/hmu/SetMode` | `{"hcmode":"auto","disablehc":"0","flowtempdesired":"20",...}` |
| Write | `ebusd/hmu/SetMode/set` | same |

## Services

### `vaillant_ebusd_mqtt.set_heating_time_program`

Sets the heating time program for one day.

```yaml
action: vaillant_ebusd_mqtt.set_heating_time_program
target:
  entity_id: climate.vaillant_heizung
data:
  day: Monday
  slots:
    - from: "06:00"
      to: "21:00"
```

Supports up to 3 slots per day. Leave `slots` empty to clear the day.

### `vaillant_ebusd_mqtt.set_hot_water_time_program`

Same as above but for the hot water circuit:

```yaml
action: vaillant_ebusd_mqtt.set_hot_water_time_program
target:
  entity_id: water_heater.vaillant_warmwasser
data:
  day: Monday
  slots:
    - from: "06:30"
      to: "20:00"
```

## State attributes

Both entities expose a `time_program` attribute with the current schedule read from ebusd:

```json
{
  "time_program": {
    "Monday": [{"from": "06:00", "to": "21:00"}],
    "Tuesday": [{"from": "06:00", "to": "21:00"}],
    ...
  }
}
```
