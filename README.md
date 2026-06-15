# Vaillant eBusd MQTT

Home Assistant custom integration for Vaillant heat pumps controlled via [ebusd](https://github.com/john30/ebusd) over MQTT.

Mirrors the **Vaillant app** structure natively in Home Assistant. Every option is read from and written to the raw ebusd MQTT topics directly — no manually-added template sensors, helpers or bridge automations required.

## Features

The integration creates **two devices**:

### Heating System
- **`climate`** entity — combined heating/cooling (HVAC mode, comfort/sleep preset, target temperatures)
- **`select`** Heating mode — `off / auto / day / night` (`Z1OpMode`)
- **`select`** Cooling mode — `off / auto / day` (`Z1OpModeCooling`)
- **`number`** Heating day / night temperature (`Z1DayTemp`, `Z1NightTemp`)
- **`number`** Cooling temperature (`Z1CoolingTemp`)
- **`calendar`** Heating schedule (`Z1Timer`) and Cooling schedule (`Z1CoolingTimer`)

### Hot Water System
- **`water_heater`** entity — operation mode (`off / auto / day`) and target temperature
- **`select`** Hot water mode (`HwcOpMode`)
- **`number`** Hot water temperature (`HwcTempDesired`)
- **`calendar`** Hot water schedule (`HwcTimer`) and Circulation schedule (`CcTimer`)

All entities share one MQTT subscription layer (local push, no polling).

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
| Entity prefix | `heating` | Used for the integration's unique id |
| MQTT base topic | `ebusd` | ebusd MQTT base; topics are read under `ebusd/700/…` |

## Topic mapping

| App option | ebusd topic (`ebusd/700/…`) |
|------------|------------------------------|
| Heating Betriebsart | `Z1OpMode` |
| Heating day / night temperature | `Z1DayTemp` / `Z1NightTemp` |
| Heating weekly planner | `Z1Timer_{Day}` |
| Cooling Betriebsart | `Z1OpModeCooling` |
| Cooling temperature | `Z1CoolingTemp` |
| Cooling weekly planner | `Z1CoolingTimer_{Day}` |
| Hot water Betriebsart | `HwcOpMode` |
| Hot water temperature | `HwcTempDesired` |
| Hot water weekly planner | `HwcTimer_{Day}` |
| Circulation weekly planner | `CcTimer_{Day}` |

> **Note:** On this VRC700 generation the app's *Heating* schedule is the zone timer
> `Z1Timer`, while `CcTimer` is the **circulation** schedule. Earlier versions of this
> integration mislabelled `CcTimer` as heating.

Timer payloads use the standard ebusd format (up to 3 windows/day, `-:-` = empty):

```json
{"from":"06:00","to":"21:00","from_2":"-:-","to_2":"-:-","from_3":"-:-","to_3":"-:-"}
```

## Weekly planners as calendars

Each weekly planner is a two-way `calendar` entity. Events are the daily comfort
windows and repeat every week. Creating, editing or deleting an event rewrites the
matching ebusd schedule. Because ebusd stores a fixed weekly pattern, edits apply to
that weekday in every week, and a day may hold at most three windows.

## Services

### `vaillant_ebusd_mqtt.set_heating_time_program`

```yaml
action: vaillant_ebusd_mqtt.set_heating_time_program
target:
  entity_id: climate.heating_system
data:
  day: Monday
  slots:
    - from: "06:00"
      to: "21:00"
```

Supports up to 3 slots per day. Leave `slots` empty to clear the day.

### `vaillant_ebusd_mqtt.set_hot_water_time_program`

Same as above but for the hot water circuit (`water_heater` entity).

### `vaillant_ebusd_mqtt.trigger_legionella_protection`

Raises the hot water setpoint to the maximum once for a legionella protection cycle.

## State attributes

The `climate` and `water_heater` entities expose a `time_program` attribute with the
current schedule read from ebusd:

```json
{
  "time_program": {
    "Monday": [{"from": "06:00", "to": "21:00"}],
    "Tuesday": [{"from": "06:00", "to": "21:00"}]
  }
}
```
