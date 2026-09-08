"""Temporary odometer input for dashboards and displays."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfLength

from .const import FUEL_FIELDS, MAX_ODOMETER
from .entity import TravelLogEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            TravelLogOdometerInput(entry.runtime_data),
            *(TravelLogFuelInput(entry.runtime_data, key) for key in FUEL_FIELDS),
        ]
    )


class TravelLogOdometerInput(TravelLogEntity, NumberEntity):
    """Require explicit input again after restart to avoid stale submissions."""

    _attr_name = "Odometer input"
    _attr_icon = "mdi:counter"
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_ODOMETER
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator):
        super().__init__(coordinator, "odometer_input")

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.coordinator.odometer_input

    async def async_set_native_value(self, value):
        self.coordinator.set_odometer(value)


class TravelLogFuelInput(TravelLogEntity, NumberEntity):
    """Unset values are omitted from the request; zero remains a real value."""

    _attr_native_min_value = 0
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:gas-station"

    def __init__(self, coordinator, key):
        super().__init__(coordinator, f"fuel_{key}")
        self.key = key
        (
            self._attr_name,
            self._attr_native_unit_of_measurement,
            self._attr_native_step,
            self._attr_native_max_value,
        ) = FUEL_FIELDS[key]

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.coordinator.fuel_inputs[self.key]

    async def async_set_native_value(self, value):
        self.coordinator.set_fuel_input(self.key, value)
