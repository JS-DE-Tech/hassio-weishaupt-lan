"""Config flow for Weishaupt WTC integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import (
    WeishauptApiClient,
    WeishauptAuthError,
    WeishauptConnectionError,
)
from .const import (
    DEFAULT_PASSWORD,
    DEFAULT_HEATING_CIRCUIT_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    CONF_HK1_NAME,
    CONF_HK2_NAME,
    CONF_HK3_NAME,
    CONF_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SCAN_INTERVAL_STEP,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=MIN_SCAN_INTERVAL,
        max=MAX_SCAN_INTERVAL,
        step=SCAN_INTERVAL_STEP,
        mode=selector.NumberSelectorMode.SLIDER,
        unit_of_measurement="s",
    )
)


def _scan_interval_default(value: Any = DEFAULT_SCAN_INTERVAL) -> int:
    """Return a valid integer scan interval for config and options forms."""
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL
    return max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, interval))


def _data_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the setup/options schema with current defaults."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)
            ): str,
            vol.Optional(
                CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            ): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=_scan_interval_default(
                    defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ),
            ): SCAN_INTERVAL_SELECTOR,
            vol.Optional(
                CONF_HK1_NAME,
                default=defaults.get(CONF_HK1_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[1]),
            ): str,
            vol.Optional(
                CONF_HK2_NAME,
                default=defaults.get(CONF_HK2_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[2]),
            ): str,
            vol.Optional(
                CONF_HK3_NAME,
                default=defaults.get(CONF_HK3_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[3]),
            ): str,
        }
    )


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the options schema with current entry data/options as defaults."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=_scan_interval_default(
                    defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ),
            ): SCAN_INTERVAL_SELECTOR,
            vol.Optional(
                CONF_HK1_NAME,
                default=defaults.get(CONF_HK1_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[1]),
            ): str,
            vol.Optional(
                CONF_HK2_NAME,
                default=defaults.get(CONF_HK2_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[2]),
            ): str,
            vol.Optional(
                CONF_HK3_NAME,
                default=defaults.get(CONF_HK3_NAME, DEFAULT_HEATING_CIRCUIT_NAMES[3]),
            ): str,
        }
    )


def _normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize selector values before storing them."""
    normalized = dict(user_input)
    normalized[CONF_SCAN_INTERVAL] = _scan_interval_default(
        normalized.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    return normalized


class WeishauptWemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Weishaupt WTC."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "WeishauptWemOptionsFlow":
        """Create the options flow."""
        return WeishauptWemOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _normalize_user_input(user_input)
            host = user_input[CONF_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            # Check if already configured
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Test connection
            session = async_get_clientsession(self.hass)
            client = WeishauptApiClient(
                host=host,
                username=username,
                password=password,
                session=session,
            )

            try:
                result = await client.test_connection()
                if not result:
                    errors["base"] = "cannot_connect"
            except WeishauptAuthError:
                errors["base"] = "invalid_auth"
            except WeishauptConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=f"Weishaupt WTC ({host})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_data_schema(user_input),
            errors=errors,
        )


class WeishauptWemOptionsFlow(OptionsFlowWithReload):
    """Handle options for Weishaupt WTC."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=_normalize_user_input(user_input),
            )

        defaults = {
            **self._config_entry.data,
            **self._config_entry.options,
        }
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(defaults),
        )
