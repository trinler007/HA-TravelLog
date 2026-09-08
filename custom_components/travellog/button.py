"""Quick actions using the explicitly entered odometer."""

from homeassistant.components.button import ButtonEntity

from .entity import TravelLogEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            TravelLogButton(entry.runtime_data, "day_end", "Day end", "mdi:flag-checkered"),
            TravelLogButton(entry.runtime_data, "fuel", "Fuel", "mdi:gas-station"),
            TravelLogResetFuel(entry.runtime_data),
        ]
    )


class TravelLogButton(TravelLogEntity, ButtonEntity):
    def __init__(self, coordinator, log_type, name, icon):
        super().__init__(coordinator, log_type)
        self.log_type = log_type
        self._attr_name = name
        self._attr_icon = icon

    async def async_press(self):
        await self.coordinator.async_quick_entry(self.log_type)


class TravelLogResetFuel(TravelLogEntity, ButtonEntity):
    _attr_name = "Reset fuel inputs"
    _attr_icon = "mdi:eraser"

    def __init__(self, coordinator):
        super().__init__(coordinator, "reset_fuel_inputs")

    @property
    def available(self):
        return True

    async def async_press(self):
        self.coordinator.reset_fuel()
