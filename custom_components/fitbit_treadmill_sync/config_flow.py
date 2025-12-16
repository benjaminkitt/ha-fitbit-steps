"""Config flow for Fitbit Treadmill Sync integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow, selector

from .const import (
    ACTIVITY_TYPES,
    CONF_ACTIVITY_TYPE,
    CONF_AUTO_SYNC,
    CONF_DISTANCE_ENTITY,
    CONF_NOTIFICATION_ENABLED,
    CONF_STATUS_ENTITY,
    CONF_STRIDE_LENGTH,
    CONF_USER_HEIGHT,
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_AUTO_SYNC,
    DEFAULT_NOTIFICATION_ENABLED,
    DEFAULT_STRIDE_MULTIPLIER,
    DOMAIN,
    INCHES_TO_FEET,
    MAX_HEIGHT,
    MAX_STRIDE,
    MIN_HEIGHT,
    MIN_STRIDE,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)

_LOGGER = logging.getLogger(__name__)


class FitbitOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Fitbit OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(["activity"])}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        # Check if Application Credentials are configured
        return await self.async_step_pick_implementation()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for Fitbit OAuth."""
        # After OAuth, proceed to entity configuration
        self.oauth_data = data
        return await self.async_step_entities()

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle entity selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that entities exist
            status_entity = user_input.get(CONF_STATUS_ENTITY)
            distance_entity = user_input.get(CONF_DISTANCE_ENTITY)

            if not self.hass.states.get(status_entity):
                errors[CONF_STATUS_ENTITY] = "entity_not_found"
            if not self.hass.states.get(distance_entity):
                errors[CONF_DISTANCE_ENTITY] = "entity_not_found"

            if not errors:
                # Store entity config and proceed to conversion settings
                self.entity_config = user_input
                return await self.async_step_conversion()

        # Show entity selection form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_STATUS_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_DISTANCE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="entities",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "status_entity_desc": "Entity that changes to 'Post-Workout' when workout completes",
                "distance_entity_desc": "Entity that shows distance in miles",
            },
        )

    async def async_step_conversion(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step conversion configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            activity_type = user_input.get(CONF_ACTIVITY_TYPE)
            stride_length = user_input.get(CONF_STRIDE_LENGTH)
            user_height = user_input.get(CONF_USER_HEIGHT)

            # Validate that either stride length or height is provided
            if stride_length is None and user_height is None:
                errors["base"] = "stride_or_height_required"
            elif stride_length is not None:
                if stride_length < MIN_STRIDE or stride_length > MAX_STRIDE:
                    errors[CONF_STRIDE_LENGTH] = "stride_out_of_range"
            elif user_height is not None:
                if user_height < MIN_HEIGHT or user_height > MAX_HEIGHT:
                    errors[CONF_USER_HEIGHT] = "height_out_of_range"

            if not errors:
                # Calculate stride from height if not provided
                if stride_length is None and user_height is not None:
                    stride_length = (user_height * DEFAULT_STRIDE_MULTIPLIER) / INCHES_TO_FEET

                # Combine all configuration
                config_data = {
                    **self.oauth_data,
                    CONF_ACTIVITY_TYPE: activity_type,
                    CONF_STRIDE_LENGTH: stride_length,
                    CONF_AUTO_SYNC: user_input.get(CONF_AUTO_SYNC, DEFAULT_AUTO_SYNC),
                    CONF_NOTIFICATION_ENABLED: user_input.get(
                        CONF_NOTIFICATION_ENABLED, DEFAULT_NOTIFICATION_ENABLED
                    ),
                }

                # Store entity config in options
                await self.async_set_unique_id(
                    f"fitbit_treadmill_{self.entity_config[CONF_STATUS_ENTITY]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Fitbit Treadmill Sync",
                    data=config_data,
                    options=self.entity_config,
                )

        # Show conversion settings form
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ACTIVITY_TYPE, default=DEFAULT_ACTIVITY_TYPE
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(ACTIVITY_TYPES.keys()),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_STRIDE_LENGTH): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_STRIDE,
                        max=MAX_STRIDE,
                        step=0.1,
                        unit_of_measurement="ft",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_USER_HEIGHT): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_HEIGHT,
                        max=MAX_HEIGHT,
                        step=1,
                        unit_of_measurement="in",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_AUTO_SYNC, default=DEFAULT_AUTO_SYNC
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_NOTIFICATION_ENABLED, default=DEFAULT_NOTIFICATION_ENABLED
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="conversion",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "stride_desc": "Your stride length in feet (optional if height provided)",
                "height_desc": "Your height in inches (optional if stride provided)",
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauthorization request."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        # Restart OAuth flow
        return await self.async_step_pick_implementation()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FitbitOptionsFlowHandler:
        """Get the options flow for this handler."""
        return FitbitOptionsFlowHandler(config_entry)


class FitbitOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Fitbit Treadmill Sync."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate entities
            status_entity = user_input.get(CONF_STATUS_ENTITY)
            distance_entity = user_input.get(CONF_DISTANCE_ENTITY)

            if not self.hass.states.get(status_entity):
                errors[CONF_STATUS_ENTITY] = "entity_not_found"
            if not self.hass.states.get(distance_entity):
                errors[CONF_DISTANCE_ENTITY] = "entity_not_found"

            # Validate stride/height
            stride_length = user_input.get(CONF_STRIDE_LENGTH)
            user_height = user_input.get(CONF_USER_HEIGHT)

            if stride_length is None and user_height is None:
                errors["base"] = "stride_or_height_required"
            elif stride_length is not None:
                if stride_length < MIN_STRIDE or stride_length > MAX_STRIDE:
                    errors[CONF_STRIDE_LENGTH] = "stride_out_of_range"
            elif user_height is not None:
                if user_height < MIN_HEIGHT or user_height > MAX_HEIGHT:
                    errors[CONF_USER_HEIGHT] = "height_out_of_range"

            if not errors:
                # Calculate stride from height if needed
                if stride_length is None and user_height is not None:
                    stride_length = (user_height * DEFAULT_STRIDE_MULTIPLIER) / INCHES_TO_FEET

                # Update config entry
                new_data = {**self.config_entry.data}
                new_data[CONF_ACTIVITY_TYPE] = user_input[CONF_ACTIVITY_TYPE]
                new_data[CONF_STRIDE_LENGTH] = stride_length
                new_data[CONF_AUTO_SYNC] = user_input[CONF_AUTO_SYNC]
                new_data[CONF_NOTIFICATION_ENABLED] = user_input[CONF_NOTIFICATION_ENABLED]

                new_options = {
                    CONF_STATUS_ENTITY: status_entity,
                    CONF_DISTANCE_ENTITY: distance_entity,
                }

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                    options=new_options,
                )

                # Trigger reload
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        # Get current values
        current_stride = self.config_entry.data.get(CONF_STRIDE_LENGTH)
        current_height = self.config_entry.data.get(CONF_USER_HEIGHT)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATUS_ENTITY,
                    default=self.config_entry.options.get(CONF_STATUS_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_DISTANCE_ENTITY,
                    default=self.config_entry.options.get(CONF_DISTANCE_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_ACTIVITY_TYPE,
                    default=self.config_entry.data.get(
                        CONF_ACTIVITY_TYPE, DEFAULT_ACTIVITY_TYPE
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(ACTIVITY_TYPES.keys()),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_STRIDE_LENGTH,
                    default=current_stride,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_STRIDE,
                        max=MAX_STRIDE,
                        step=0.1,
                        unit_of_measurement="ft",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_USER_HEIGHT,
                    default=current_height,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_HEIGHT,
                        max=MAX_HEIGHT,
                        step=1,
                        unit_of_measurement="in",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_AUTO_SYNC,
                    default=self.config_entry.data.get(CONF_AUTO_SYNC, DEFAULT_AUTO_SYNC),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_NOTIFICATION_ENABLED,
                    default=self.config_entry.data.get(
                        CONF_NOTIFICATION_ENABLED, DEFAULT_NOTIFICATION_ENABLED
                    ),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
