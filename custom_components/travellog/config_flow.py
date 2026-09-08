"""Configure TravelLog with a URL and API key."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import TravelLogAuthError, TravelLogClient, TravelLogError, normalize_url
from .const import DOMAIN


class TravelLogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One config entry per application URL."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                url = normalize_url(user_input[CONF_URL])
                client = TravelLogClient(
                    async_get_clientsession(self.hass), url, user_input[CONF_API_KEY]
                )
                await client.fetch()
            except ValueError:
                errors["base"] = "invalid_url"
            except TravelLogAuthError:
                errors["base"] = "invalid_auth"
            except TravelLogError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="TravelLog", data={**user_input, CONF_URL: url}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            try:
                await TravelLogClient(
                    async_get_clientsession(self.hass),
                    entry.data[CONF_URL],
                    user_input[CONF_API_KEY],
                ).fetch()
            except TravelLogAuthError:
                errors["base"] = "invalid_auth"
            except TravelLogError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )
