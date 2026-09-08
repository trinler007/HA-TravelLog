"""Full-tank checkbox represented as a native HA toggle."""

from homeassistant.components.switch import SwitchEntity

from .entity import TravelLogEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TravelLogFullTank(entry.runtime_data)])


class TravelLogFullTank(TravelLogEntity, SwitchEntity):
    _attr_name = "Fuel full tank"
    _attr_icon = "mdi:gas-station"

    def __init__(self, coordinator):
        super().__init__(coordinator, "fuel_full_tank")

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.full_tank

    async def async_turn_on(self, **kwargs):
        self.coordinator.set_full_tank(True)

    async def async_turn_off(self, **kwargs):
        self.coordinator.set_full_tank(False)
