"""Quick actions using the explicitly entered odometer."""

from homeassistant.components.button import ButtonEntity

from .entity import TravelLogEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            TravelLogButton(entry.runtime_data, "day_end", "Day end", "mdi:flag-checkered"),
            TravelLogButton(entry.runtime_data, "fuel", "Fuel", "mdi:gas-station"),
        ]
    )


class TravelLogButton(TravelLogEntity, ButtonEntity):
    def __init__(self, coordinator, log_type, name, icon):
        super().__init__(coordinator, log_type)
        self.log_type = log_type
        self._attr_name = name
        self._attr_icon = icon

    async def async_press(self):
        await self.coordinator.async_write({"log_type": self.log_type})
