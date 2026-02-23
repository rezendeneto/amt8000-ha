"""Config flow for AMT-8000 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_AWAY_PARTITIONS,
    CONF_HOST,
    CONF_NIGHT_PARTITIONS,
    CONF_NUM_PARTITIONS,
    CONF_NUM_ZONES,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_STAY_PARTITIONS,
    DEFAULT_NUM_PARTITIONS,
    DEFAULT_NUM_ZONES,
    DEFAULT_PORT,
    DOMAIN,
)
from .isec2 import AuthError, CommunicationError, test_connection

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_NUM_ZONES, default=DEFAULT_NUM_ZONES): vol.All(
            int, vol.Range(min=1, max=64)
        ),
        vol.Optional(CONF_NUM_PARTITIONS, default=DEFAULT_NUM_PARTITIONS): vol.All(
            int, vol.Range(min=1, max=16)
        ),
        vol.Optional(CONF_AWAY_PARTITIONS, default="0"): str,
        vol.Optional(CONF_STAY_PARTITIONS, default=""): str,
        vol.Optional(CONF_NIGHT_PARTITIONS, default=""): str,
    }
)


def _parse_partition_list(value: str) -> list[int]:
    """Parse a comma-separated string of partition numbers."""
    if not value or not value.strip():
        return []
    parts = []
    for part in value.split(","):
        part = part.strip()
        if part:
            try:
                parts.append(int(part))
            except ValueError:
                pass
    return parts


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    try:
        await test_connection(data[CONF_HOST], data[CONF_PORT], data[CONF_PASSWORD])
    except CommunicationError as err:
        raise CannotConnect(str(err)) from err
    except AuthError as err:
        raise InvalidAuth(str(err)) from err

    return {"title": f"AMT-8000 ({data[CONF_HOST]})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AMT-8000."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Parse partition lists
            user_input[CONF_AWAY_PARTITIONS] = _parse_partition_list(
                user_input.get(CONF_AWAY_PARTITIONS, "0")
            )
            user_input[CONF_STAY_PARTITIONS] = _parse_partition_list(
                user_input.get(CONF_STAY_PARTITIONS, "")
            )
            user_input[CONF_NIGHT_PARTITIONS] = _parse_partition_list(
                user_input.get(CONF_NIGHT_PARTITIONS, "")
            )

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Set unique ID based on host to prevent duplicates
                await self.async_set_unique_id(
                    f"amt8000_{user_input[CONF_HOST]}_{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for AMT-8000."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NUM_ZONES,
                        default=current.get(CONF_NUM_ZONES, DEFAULT_NUM_ZONES),
                    ): vol.All(int, vol.Range(min=1, max=64)),
                    vol.Optional(
                        CONF_NUM_PARTITIONS,
                        default=current.get(CONF_NUM_PARTITIONS, DEFAULT_NUM_PARTITIONS),
                    ): vol.All(int, vol.Range(min=1, max=16)),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
