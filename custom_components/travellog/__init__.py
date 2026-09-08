"""TravelLog integration and logbook action."""

import math

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TravelLogClient
from .const import DOMAIN, LOG_TYPES, MAX_ODOMETER, PLATFORMS
from .coordinator import TravelLogCoordinator


def nonnegative(value):
    """Reject NaN, infinity, booleans and negative financial/distance values."""
    if isinstance(value, bool):
        raise vol.Invalid("Expected a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid("Expected a number") from err
    if not math.isfinite(result) or result < 0:
        raise vol.Invalid("Expected a finite nonnegative number")
    return result


SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): str,
        vol.Required("log_type"): vol.In(LOG_TYPES),
        vol.Required("odometer_km"): vol.All(nonnegative, vol.Range(max=MAX_ODOMETER)),
        vol.Optional("occurred_on"): vol.All(cv.date, lambda value: value.isoformat()),
        vol.Optional("vendor"): vol.All(str, vol.Length(max=180)),
        vol.Optional("country_code"): vol.All(str, vol.Upper, vol.Match(r"^[A-Z]{2}$")),
        vol.Optional("liters"): nonnegative,
        vol.Optional("price_per_liter"): nonnegative,
        vol.Optional("is_full_tank"): cv.boolean,
        vol.Optional("amount"): nonnegative,
        vol.Optional("currency"): vol.All(str, vol.Upper, vol.Match(r"^[A-Z]{3}$")),
        vol.Optional("performed_by"): vol.All(str, vol.Length(max=180)),
        vol.Optional("notes"): vol.All(str, vol.Length(max=10000)),
    }
)


async def async_setup(hass, config):
    """Register actions even if an entry is currently unavailable."""

    async def add_logbook_entry(call):
        data = dict(call.data)
        entry_id = data.pop("config_entry_id", None)
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if entry_id is None or e.entry_id == entry_id
        ]
        if len(entries) != 1 or entries[0].state is not ConfigEntryState.LOADED:
            raise HomeAssistantError("Select one loaded TravelLog config entry")
        result = await entries[0].runtime_data.async_write(data)
        return result if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        "add_logbook_entry",
        add_logbook_entry,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass, entry):
    client = TravelLogClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_API_KEY]
    )
    coordinator = TravelLogCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
