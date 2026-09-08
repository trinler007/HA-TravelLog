"""TravelLog constants."""

DOMAIN = "travellog"
PLATFORMS = ["sensor", "number", "button", "switch"]
CONF_LOCATION_ENTITY = "location_entity"
DEFAULT_LOCATION_ENTITY = "sensor.nx_01_position_gps_location"
FUEL_FIELDS = {
    "liters": ("Fuel liters", "L", 0.01, 10000),
    "price_per_liter": ("Fuel price per liter", "EUR/L", 0.001, 10000),
    "amount": ("Fuel total price", "EUR", 0.01, 1000000),
}
LOG_TYPES = ("day_end", "fuel", "maintenance", "repair", "cost", "odometer")
MAX_ODOMETER = 9999999
