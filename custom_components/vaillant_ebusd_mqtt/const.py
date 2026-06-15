DOMAIN = "vaillant_ebusd_mqtt"

CONF_ENTITY_PREFIX = "entity_prefix"
CONF_MQTT_PREFIX = "mqtt_prefix"

DEFAULT_ENTITY_PREFIX = "heating"
DEFAULT_MQTT_PREFIX = "ebusd"

# ebusd circuit address appended to the MQTT base prefix (ebusd/700/...)
CIRCUIT = "700"

# English day names as used in the ebusd timer topic suffixes (CcTimer_Monday, ...)
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# Map weekday index (Mon=0) -> ebusd day name
WEEKDAY_TO_DAY = {i: day for i, day in enumerate(DAYS)}

# ebusd timer JSON carries up to three windows per day, suffixed "", "_2", "_3"
SLOT_SUFFIXES = ["", "_2", "_3"]
EMPTY = "-:-"
MAX_SLOTS = 3

# --- Two logical devices ---------------------------------------------------
DEVICE_HEATING = "heating"
DEVICE_HOT_WATER = "hot_water"
DEVICE_NAMES = {
    DEVICE_HEATING: "Heating System",
    DEVICE_HOT_WATER: "Hot Water System",
}

# --- Writable scalar topics (relative to ebusd/700) ------------------------
T_Z1_OPMODE = "Z1OpMode"            # heating Betriebsart: off/auto/day/night
T_Z1_OPMODE_COOLING = "Z1OpModeCooling"  # cooling Betriebsart: off/auto/day
T_Z1_DAY_TEMP = "Z1DayTemp"
T_Z1_NIGHT_TEMP = "Z1NightTemp"
T_Z1_COOLING_TEMP = "Z1CoolingTemp"
T_HWC_OPMODE = "HwcOpMode"          # hot water Betriebsart: off/auto/day
T_HWC_TEMP_DESIRED = "HwcTempDesired"

# --- Read-only scalar topics (for climate/water_heater current values) -----
T_Z1_ROOM_TEMP = "Z1RoomTemp"
T_ROOM_HUMIDITY = "RoomHumidity"
T_OUTSIDE_TEMP = "DisplayedOutsideTemp"
T_HWC_STORAGE_TEMP = "HwcStorageTemp"

SCALAR_TOPICS = [
    T_Z1_OPMODE,
    T_Z1_OPMODE_COOLING,
    T_Z1_DAY_TEMP,
    T_Z1_NIGHT_TEMP,
    T_Z1_COOLING_TEMP,
    T_HWC_OPMODE,
    T_HWC_TEMP_DESIRED,
    T_Z1_ROOM_TEMP,
    T_ROOM_HUMIDITY,
    T_OUTSIDE_TEMP,
    T_HWC_STORAGE_TEMP,
]

# --- Timer (weekly planner) topics -----------------------------------------
T_HEATING_TIMER = "Z1Timer"          # heating weekly planner
T_COOLING_TIMER = "Z1CoolingTimer"   # cooling weekly planner
T_HWC_TIMER = "HwcTimer"             # hot water weekly planner
# circulation weekly planner (app "Zirkulation"); CcTimer, not heating
T_CIRC_TIMER = "CcTimer"

TIMER_TOPICS = [T_HEATING_TIMER, T_COOLING_TIMER, T_HWC_TIMER, T_CIRC_TIMER]

# HMU heat-management-unit state topic, relative to the MQTT base prefix
HMU_STATE_SUFFIX = "hmu/State"

# --- Option lists (mirroring the Vaillant app) -----------------------------
HEATING_MODES = ["off", "auto", "day", "night"]
COOLING_MODES = ["off", "auto", "day"]
HOT_WATER_MODES = ["off", "auto", "day"]

# --- Sensible temperature ranges (ebusd reports min=-50/max=180) ------------
HEATING_MIN_TEMP = 5.0
HEATING_MAX_TEMP = 30.0
COOLING_MIN_TEMP = 15.0
COOLING_MAX_TEMP = 30.0
HWC_MIN_TEMP = 35.0
HWC_MAX_TEMP = 70.0
TEMP_STEP = 0.5
