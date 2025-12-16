"""The Fitbit Treadmill Sync integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api import FitbitAPI
from .const import (
    CONF_OAUTH_ACCESS_TOKEN,
    CONF_OAUTH_EXPIRES_AT,
    CONF_OAUTH_REFRESH_TOKEN,
    DOMAIN,
    SERVICE_SYNC_WORKOUT,
)
from .coordinator import FitbitTreadmillCoordinator

_LOGGER = logging.getLogger(__name__)

# Service schema
SYNC_WORKOUT_SCHEMA = vol.Schema(
    {
        vol.Optional("distance"): cv.positive_float,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fitbit Treadmill Sync from a config entry."""
    _LOGGER.debug("Setting up Fitbit Treadmill Sync")

    # Extract OAuth tokens from config entry
    token_data = entry.data.get("token", {})
    access_token = token_data.get(CONF_OAUTH_ACCESS_TOKEN)
    refresh_token = token_data.get(CONF_OAUTH_REFRESH_TOKEN)
    expires_at = token_data.get(CONF_OAUTH_EXPIRES_AT, 0)

    # Get OAuth client credentials from implementation
    implementation = entry.data.get("auth_implementation")

    # Try to get client credentials from the entry data
    client_id = entry.data.get(CONF_CLIENT_ID)
    client_secret = entry.data.get(CONF_CLIENT_SECRET)

    if not client_id or not client_secret:
        _LOGGER.error("OAuth client credentials not found in config entry")
        return False

    # Create API client
    api = FitbitAPI(
        hass=hass,
        entry=entry,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        client_id=client_id,
        client_secret=client_secret,
    )

    # Validate API connection
    try:
        await api.get_user_profile()
        _LOGGER.info("Successfully connected to Fitbit API")
    except Exception as err:
        _LOGGER.error("Failed to connect to Fitbit API: %s", err)
        return False

    # Create coordinator
    coordinator = FitbitTreadmillCoordinator(
        hass=hass,
        entry=entry,
        api=api,
    )

    # Set up state listeners
    await coordinator.async_setup()

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # Register services
    async def handle_sync_workout(call: ServiceCall) -> None:
        """Handle manual sync service call."""
        distance = call.data.get("distance")

        try:
            result = await coordinator.manual_sync(distance_override=distance)
            _LOGGER.info("Manual sync successful: %s", result)
        except Exception as err:
            _LOGGER.error("Manual sync failed: %s", err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_WORKOUT,
        handle_sync_workout,
        schema=SYNC_WORKOUT_SCHEMA,
    )

    _LOGGER.info("Fitbit Treadmill Sync setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Fitbit Treadmill Sync")

    # Get coordinator
    data = hass.data[DOMAIN].pop(entry.entry_id)
    coordinator = data["coordinator"]

    # Unload coordinator
    await coordinator.async_unload()

    # Unregister services (only if this is the last entry)
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_SYNC_WORKOUT)

    _LOGGER.info("Fitbit Treadmill Sync unloaded")
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
