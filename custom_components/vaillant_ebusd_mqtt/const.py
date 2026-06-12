DOMAIN = "vaillant_ebusd_mqtt"

# Config entry keys
CONF_MQTT_PREFIX = "mqtt_prefix"
CONF_HMU_PREFIX = "hmu_prefix"
CONF_HEATING_NAME = "heating_name"
CONF_HOT_WATER_NAME = "hot_water_name"
CONF_FLOW_TEMP_TOPIC = "flow_temp_topic"
CONF_ROOM_TEMP_TOPIC = "room_temp_topic"
CONF_OUTDOOR_TEMP_TOPIC = "outdoor_temp_topic"
CONF_HWC_STORAGE_TEMP_TOPIC = "hwc_storage_temp_topic"

# Defaults
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

SLOT_SUFFIXES = ["", "_2", "_3"]

# ebusd hcmode values
EBUSD_MODE_AUTO = "auto"
EBUSD_MODE_DAY = "day"
EBUSD_MODE_NIGHT = "night"
EBUSD_MODE_OFF = "off"

# Coordinator attribute names (shared between coordinator and entity descriptions)
ATTR_FLOW_TEMP_DESIRED = "flow_temp_desired"
ATTR_HWC_TEMP_DESIRED = "hwc_temp_desired"
ATTR_HWC_FLOW_TEMP_DESIRED = "hwc_flow_temp_desired"
ATTR_HC_MODE = "hc_mode"
ATTR_ENERGY_SUM = "energy_sum"
ATTR_DISABLE_HC = "disable_hc"
ATTR_DISABLE_HWC_LOAD = "disable_hwc_load"
ATTR_DISABLE_HWC_TAPPING = "disable_hwc_tapping"
ATTR_HMU_ON = "hmu_on"
ATTR_CIR_PUMP_ACTIVE = "cir_pump_active"
ATTR_HC_MODE_ACTIVE = "hc_mode_active"
ATTR_HWC_MODE_ACTIVE = "hwc_mode_active"
ATTR_CURRENT_FLOW_TEMP = "current_flow_temp"
ATTR_CURRENT_ROOM_TEMP = "current_room_temp"
ATTR_CURRENT_OUTDOOR_TEMP = "current_outdoor_temp"
ATTR_CURRENT_HWC_STORAGE_TEMP = "current_hwc_storage_temp"
