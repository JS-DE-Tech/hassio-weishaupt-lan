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
    CONF_DETECTED_HEATING_CIRCUIT_NAMES,
    CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
    CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
    DEFAULT_PASSWORD,
    DEFAULT_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
    DEFAULT_ENABLE_EXPERIMENTAL_WTC_SENSORS,
    DEFAULT_HEATING_CIRCUIT_NAMES,
    DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    CONF_HK1_NAME,
    CONF_HK2_NAME,
    CONF_HK3_NAME,
    CONF_SCAN_INTERVAL,
    CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SCAN_INTERVAL_STEP,
)
from .heating_circuits import (
    heating_circuit_names_from_config,
    heating_circuit_names_from_systable_csv,
    serialize_heating_circuit_names,
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
                CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
                default=defaults.get(
                    CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
                    DEFAULT_ENABLE_EXPERIMENTAL_WTC_SENSORS,
                ),
            ): bool,
            vol.Optional(
                CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
                default=defaults.get(
                    CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
                    DEFAULT_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
                ),
            ): bool,
        }
    )


def _names_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the heating-circuit naming schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                default=defaults.get(
                    CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                    DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                ),
            ): bool,
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
                CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                default=defaults.get(
                    CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                    DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                ),
            ): bool,
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
            vol.Optional(
                CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
                default=defaults.get(
                    CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
                    DEFAULT_ENABLE_EXPERIMENTAL_WTC_SENSORS,
                ),
            ): bool,
            vol.Optional(
                CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
                default=defaults.get(
                    CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
                    DEFAULT_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
                ),
            ): bool,
        }
    )


def _normalize_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize selector values before storing them."""
    normalized = dict(user_input)
    normalized[CONF_SCAN_INTERVAL] = _scan_interval_default(
        normalized.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    normalized[CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS] = bool(
        normalized.get(
            CONF_ENABLE_EXPERIMENTAL_WTC_SENSORS,
            DEFAULT_ENABLE_EXPERIMENTAL_WTC_SENSORS,
        )
    )
    normalized[CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS] = bool(
        normalized.get(
            CONF_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
            DEFAULT_ENABLE_EXTENDED_EXPERIMENTAL_WTC_SENSORS,
        )
    )
    normalized[CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES] = bool(
        normalized.get(
            CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
            DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
        )
    )
    for key in (CONF_HK1_NAME, CONF_HK2_NAME, CONF_HK3_NAME):
        if key in normalized and normalized[key] is not None:
            normalized[key] = str(normalized[key]).strip()
    return normalized


def _manual_name_overrides_from_defaults(defaults: dict[str, Any]) -> dict[str, str]:
    """Return configured manual heating-circuit name overrides."""
    return {
        CONF_HK1_NAME: str(defaults.get(CONF_HK1_NAME, "") or "").strip(),
        CONF_HK2_NAME: str(defaults.get(CONF_HK2_NAME, "") or "").strip(),
        CONF_HK3_NAME: str(defaults.get(CONF_HK3_NAME, "") or "").strip(),
    }


def _name_defaults_from_detected(
    detected_names: dict[int, str],
    manual_overrides: dict[str, str] | None = None,
    use_detected_names: bool = DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
) -> dict[str, Any]:
    """Return form defaults for heating-circuit names."""
    manual_overrides = manual_overrides or {}
    return {
        CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES: use_detected_names,
        CONF_HK1_NAME: manual_overrides.get(CONF_HK1_NAME)
        or detected_names.get(1, DEFAULT_HEATING_CIRCUIT_NAMES[1]),
        CONF_HK2_NAME: manual_overrides.get(CONF_HK2_NAME)
        or detected_names.get(2, DEFAULT_HEATING_CIRCUIT_NAMES[2]),
        CONF_HK3_NAME: manual_overrides.get(CONF_HK3_NAME)
        or detected_names.get(3, DEFAULT_HEATING_CIRCUIT_NAMES[3]),
    }


async def _async_fetch_detected_heating_circuit_names(
    client: WeishauptApiClient,
) -> dict[int, str] | None:
    """Fetch systable.csv and parse detected heating-circuit names."""
    try:
        systable_csv = await client.fetch_systable_csv()
    except Exception:
        _LOGGER.debug("Could not fetch systable.csv for detected names", exc_info=True)
        return None
    if systable_csv is None:
        _LOGGER.debug("systable.csv unavailable for detected-name refresh")
        return None
    detected_names = heating_circuit_names_from_systable_csv(systable_csv)
    _LOGGER.debug(
        "Fetched systable.csv for detected-name refresh: chars=%s names=%s",
        len(systable_csv),
        detected_names,
    )
    return detected_names


class WeishauptWemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Weishaupt WTC."""

    VERSION = 1
    _pending_user_input: dict[str, Any] | None = None
    _detected_heating_circuit_names: dict[int, str]

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
                detected_names = (
                    await _async_fetch_detected_heating_circuit_names(client)
                ) or {}
                self._pending_user_input = user_input
                self._detected_heating_circuit_names = detected_names
                return self.async_show_form(
                    step_id="names",
                    data_schema=_names_schema(
                        _name_defaults_from_detected(
                            self._detected_heating_circuit_names
                        )
                    ),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_data_schema(user_input),
            errors=errors,
        )

    async def async_step_names(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle detected and editable heating-circuit names."""
        if user_input is None:
            return self.async_show_form(
                step_id="names",
                data_schema=_names_schema(
                    _name_defaults_from_detected(
                        getattr(self, "_detected_heating_circuit_names", {})
                    )
                ),
            )
        base_input = self._pending_user_input or {}
        normalized = _normalize_user_input({**base_input, **user_input})
        normalized[CONF_DETECTED_HEATING_CIRCUIT_NAMES] = (
            serialize_heating_circuit_names(
                getattr(self, "_detected_heating_circuit_names", {})
            )
        )
        host = normalized[CONF_HOST]
        return self.async_create_entry(
            title=f"Weishaupt WTC ({host})",
            data=normalized,
        )


class WeishauptWemOptionsFlow(OptionsFlowWithReload):
    """Handle options for Weishaupt WTC."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry
        self._detected_heating_circuit_names = heating_circuit_names_from_config(
            config_entry.data.get(CONF_DETECTED_HEATING_CIRCUIT_NAMES, {})
        )

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
        detected_names = self._detected_heating_circuit_names
        host = self._config_entry.data.get(CONF_HOST)
        username = self._config_entry.data.get(CONF_USERNAME)
        password = self._config_entry.data.get(CONF_PASSWORD)
        if host and username and password:
            session = async_get_clientsession(self.hass)
            client = WeishauptApiClient(
                host=host,
                username=username,
                password=password,
                session=session,
            )
            refreshed_names = await _async_fetch_detected_heating_circuit_names(client)
            if refreshed_names is not None:
                detected_names = refreshed_names
                self._detected_heating_circuit_names = detected_names
                updated_data = {
                    **self._config_entry.data,
                    CONF_DETECTED_HEATING_CIRCUIT_NAMES: serialize_heating_circuit_names(
                        detected_names
                    ),
                }
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data=updated_data,
                )
                defaults[CONF_DETECTED_HEATING_CIRCUIT_NAMES] = updated_data[
                    CONF_DETECTED_HEATING_CIRCUIT_NAMES
                ]
        manual_overrides = _manual_name_overrides_from_defaults(defaults)
        name_defaults = _name_defaults_from_detected(
            detected_names,
            manual_overrides,
            bool(
                defaults.get(
                    CONF_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                    DEFAULT_USE_DETECTED_HEATING_CIRCUIT_NAMES,
                )
            ),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema({**defaults, **name_defaults}),
        )
