"""Polling and serialized, explicitly confirmed writes."""

import asyncio
import logging
import math
import time
from datetime import timedelta

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TravelLogAuthError, TravelLogError, TravelLogWriteUncertain
from .const import CONF_LOCATION_ENTITY, DEFAULT_LOCATION_ENTITY, DOMAIN, FUEL_FIELDS, MAX_ODOMETER

_LOGGER = logging.getLogger(__name__)


class TravelLogCoordinator(DataUpdateCoordinator):
    """Hold shared data and the temporary odometer input."""

    def __init__(self, hass, entry, client):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5))
        self.entry = entry
        self.client = client
        self.odometer_input = None
        self.fuel_inputs = dict.fromkeys(FUEL_FIELDS)
        self.full_tank = False
        self._last_quick_entry = None
        self._last_quick_time = 0.0
        self.write_status = "idle"
        self.last_result = None
        self._write_lock = asyncio.Lock()
        self._last_payload = None
        self._last_write = 0.0

    async def _async_update_data(self):
        try:
            return await self.client.fetch()
        except TravelLogAuthError as err:
            raise ConfigEntryAuthFailed("TravelLog API key rejected") from err
        except TravelLogError as err:
            raise UpdateFailed(str(err)) from err

    def set_odometer(self, value):
        """Input is a draft; editing never sends a request."""
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= MAX_ODOMETER:
            raise HomeAssistantError("Invalid odometer value")
        self.odometer_input = value
        self.async_update_listeners()

    def set_fuel_input(self, key, value):
        """Keep optional values distinct from explicitly entered zero."""
        if self._write_lock.locked():
            raise HomeAssistantError("A TravelLog entry is already being saved")
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= FUEL_FIELDS[key][3]:
            raise HomeAssistantError("Invalid fuel value")
        self.fuel_inputs[key] = value
        self.async_update_listeners()

    def set_full_tank(self, value):
        if self._write_lock.locked():
            raise HomeAssistantError("A TravelLog entry is already being saved")
        self.full_tank = value
        self.async_update_listeners()

    def reset_fuel(self):
        """Clear the draft without creating an entry."""
        if self._write_lock.locked():
            raise HomeAssistantError("A TravelLog entry is already being saved")
        self.fuel_inputs = dict.fromkeys(FUEL_FIELDS)
        self.full_tank = False
        self.async_update_listeners()

    async def async_quick_entry(self, log_type):
        """Build a button payload from the current local draft."""
        if self.odometer_input is None:
            raise HomeAssistantError("Enter the current odometer first")
        signature = (log_type, self.odometer_input)
        if self._last_quick_entry == signature and time.monotonic() - self._last_quick_time < 30:
            raise HomeAssistantError("Repeated entry blocked for 30 seconds")
        payload = {"log_type": log_type, "odometer_km": self.odometer_input}
        if log_type == "day_end":
            entity_id = self.entry.options.get(CONF_LOCATION_ENTITY, DEFAULT_LOCATION_ENTITY)
            if entity_id:
                state = self.hass.states.get(entity_id)
                if state is None or state.state.strip().lower() in ("", "unknown", "unavailable"):
                    raise HomeAssistantError(f"Location sensor {entity_id} is unavailable")
                destination = state.state.strip()
                if len(destination) > 180:
                    raise HomeAssistantError("Destination exceeds TravelLog's 180 character limit")
                payload["vendor"] = destination
        elif log_type == "fuel":
            payload.update(
                {key: value for key, value in self.fuel_inputs.items() if value is not None}
            )
            payload["is_full_tank"] = self.full_tank
        else:
            raise HomeAssistantError("Unsupported quick entry type")
        self._last_quick_entry = signature
        self._last_quick_time = time.monotonic()
        result = await self.async_write(payload)
        if log_type == "fuel":
            self.reset_fuel()
        return result

    async def async_write(self, payload):
        """Suppress rapid repeated taps; never retry an uncertain POST."""
        if self._write_lock.locked():
            raise HomeAssistantError("A TravelLog entry is already being saved")
        async with self._write_lock:
            payload = dict(payload)
            if "odometer_km" not in payload:
                if self.odometer_input is None:
                    raise HomeAssistantError("Enter the current odometer first")
                payload["odometer_km"] = self.odometer_input
            if self._last_payload == payload and time.monotonic() - self._last_write < 30:
                raise HomeAssistantError("Repeated entry blocked for 30 seconds")
            self._last_payload = payload
            self._last_write = time.monotonic()
            self.write_status = "saving"
            self.async_update_listeners()
            try:
                result = await self.client.request("POST", "logbook", payload)
            except TravelLogError as err:
                self.write_status = (
                    "uncertain" if isinstance(err, TravelLogWriteUncertain) else "error"
                )
                self.async_update_listeners()
                if isinstance(err, TravelLogAuthError):
                    self.entry.async_start_reauth(self.hass)
                raise HomeAssistantError(str(err)) from err
            self.last_result = result
            self.write_status = "needs_review" if result["needs_review"] else "saved"
            self.async_update_listeners()
            self.hass.bus.async_fire(
                f"{DOMAIN}_logbook_created", {"entry_id": self.entry.entry_id, **result}
            )
            # A failed follow-up GET must never turn a confirmed save into a failed POST.
            await self.async_request_refresh()
            return result
