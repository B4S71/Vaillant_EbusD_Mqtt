DOMAIN = "vaillant_ebusd_mqtt"

CONF_MQTT_PREFIX = "mqtt_prefix"
CONF_HMU_PREFIX = "hmu_prefix"
CONF_HEATING_NAME = "heating_name"
CONF_HOT_WATER_NAME = "hot_water_name"

DEFAULT_MQTT_PREFIX = "ebusd/700"
DEFAULT_HMU_PREFIX = "ebusd/hmu"
DEFAULT_HEATING_NAME = "Vaillant Heizung"
DEFAULT_HOT_WATER_NAME = "Vaillant Warmwasser"

DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

# Suffixes for the three timer slots per day
SLOT_SUFFIXES = ["", "_2", "_3"]

# ebusd hcmode values
EBUSD_MODE_AUTO = "auto"
EBUSD_MODE_DAY = "day"
EBUSD_MODE_NIGHT = "night"
EBUSD_MODE_OFF = "off"
