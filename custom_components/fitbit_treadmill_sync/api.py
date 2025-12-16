"""Fitbit API client for Treadmill Sync integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import time
from typing import Any

import fitbit
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    ACTIVITY_TYPES,
    CONF_OAUTH_ACCESS_TOKEN,
    CONF_OAUTH_EXPIRES_AT,
    CONF_OAUTH_REFRESH_TOKEN,
    FEET_PER_MILE,
    TOKEN_REFRESH_BUFFER,
)

_LOGGER = logging.getLogger(__name__)


class FitbitAPIError(Exception):
    """Base exception for Fitbit API errors."""


class RateLimitError(FitbitAPIError):
    """Rate limit exceeded."""


class FitbitAPI:
    """Wrapper for Fitbit API interactions."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        access_token: str,
        refresh_token: str,
        expires_at: float,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize Fitbit API client."""
        self.hass = hass
        self.entry = entry
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.client_id = client_id
        self.client_secret = client_secret

        # Initialize Fitbit client
        self.client = fitbit.Fitbit(
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            system="en_US",
        )

        # Rate limiting
        self._request_times: list[float] = []

    async def _ensure_token_valid(self) -> None:
        """Ensure OAuth token is valid, refresh if needed."""
        current_time = time.time()

        # Check if token needs refresh (5 min buffer)
        if current_time >= self.expires_at - TOKEN_REFRESH_BUFFER:
            _LOGGER.debug("Access token expired or expiring soon, refreshing")
            await self._refresh_token()

    async def _refresh_token(self) -> None:
        """Refresh OAuth token."""
        try:
            # Refresh token using fitbit library
            token_data = await self.hass.async_add_executor_job(
                self.client.client.refresh_token
            )

            # Update stored tokens
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data["refresh_token"]
            self.expires_at = time.time() + token_data["expires_in"]

            # Update config entry
            new_data = {**self.entry.data}
            new_data["token"] = {
                CONF_OAUTH_ACCESS_TOKEN: self.access_token,
                CONF_OAUTH_REFRESH_TOKEN: self.refresh_token,
                CONF_OAUTH_EXPIRES_AT: self.expires_at,
            }

            self.hass.config_entries.async_update_entry(
                self.entry,
                data=new_data,
            )

            _LOGGER.info("Successfully refreshed Fitbit OAuth token")

        except Exception as err:
            _LOGGER.error("Failed to refresh token: %s", err)
            raise ConfigEntryAuthFailed("Token refresh failed") from err

    async def _check_rate_limit(self) -> None:
        """Check if we're within rate limits."""
        current_time = time.time()

        # Remove requests older than 1 hour
        self._request_times = [
            t for t in self._request_times if current_time - t < 3600
        ]

        # Check if we would exceed rate limit
        if len(self._request_times) >= 150:  # Fitbit: 150 req/hour
            raise RateLimitError("Fitbit API rate limit would be exceeded")

        # Add current request time
        self._request_times.append(current_time)

    async def convert_distance_to_steps(
        self,
        distance_miles: float,
        stride_feet: float,
        activity_type: str,
    ) -> tuple[int, str]:
        """Convert distance to steps with fallback.

        Args:
            distance_miles: Distance in miles
            stride_feet: User's stride length in feet (for fallback)
            activity_type: Type of activity (Walking, Running, Treadmill)

        Returns:
            tuple of (steps, conversion_method)
            where conversion_method is either "fitbit_api" or "manual_calculation"
        """
        # Method 1: Try Fitbit API conversion
        # Note: Fitbit's Create Activity Log API may automatically calculate steps
        # from distance. We'll check the response after creating the activity.
        # For now, we'll use manual calculation as the primary method since
        # the API behavior is not explicitly documented.

        _LOGGER.debug(
            "Using manual step conversion: %.2f miles, %.2f ft stride",
            distance_miles,
            stride_feet,
        )

        # Method 2: Manual calculation
        distance_feet = distance_miles * FEET_PER_MILE
        steps = int(distance_feet / stride_feet)

        _LOGGER.info(
            "Converted %.2f miles to %d steps using manual calculation",
            distance_miles,
            steps,
        )

        return steps, "manual_calculation"

    async def create_activity_log(
        self,
        activity_type: str,
        distance_miles: float,
        start_time: datetime,
        duration_minutes: int,
        steps: int | None = None,
    ) -> dict[str, Any]:
        """Create activity log in Fitbit.

        Args:
            activity_type: Type of activity (Walking, Running, Treadmill)
            distance_miles: Distance in miles
            start_time: When the workout started
            duration_minutes: Duration in minutes
            steps: Optional step count to include

        Returns:
            Response from Fitbit API containing the created activity log

        Raises:
            ConfigEntryAuthFailed: If authentication fails
            RateLimitError: If rate limit is exceeded
            FitbitAPIError: For other API errors
        """
        # Ensure token is valid
        await self._ensure_token_valid()

        # Check rate limit
        await self._check_rate_limit()

        # Get activity ID from type
        activity_id = ACTIVITY_TYPES.get(activity_type, ACTIVITY_TYPES["Walking"])

        # Prepare activity data
        activity_data = {
            "activityId": activity_id,
            "startTime": start_time.strftime("%H:%M"),
            "durationMillis": duration_minutes * 60 * 1000,
            "date": start_time.strftime("%Y-%m-%d"),
            "distance": distance_miles,
            "distanceUnit": "mi",
        }

        # Include steps if provided
        # Note: Fitbit may calculate steps automatically from distance
        # but we can include our calculated value
        if steps is not None:
            activity_data["steps"] = steps

        _LOGGER.debug("Creating Fitbit activity log: %s", activity_data)

        try:
            # Make API call
            response = await self.hass.async_add_executor_job(
                self.client.activities, data=activity_data
            )

            _LOGGER.info(
                "Successfully created Fitbit activity: %s, %.2f miles, %s steps",
                activity_type,
                distance_miles,
                steps if steps else "auto-calculated",
            )

            return response

        except fitbit.exceptions.HTTPUnauthorized as err:
            _LOGGER.error("Fitbit authentication failed: %s", err)
            raise ConfigEntryAuthFailed("Authentication failed") from err

        except fitbit.exceptions.HTTPTooManyRequests as err:
            _LOGGER.warning("Fitbit rate limit exceeded: %s", err)
            raise RateLimitError("Rate limit exceeded") from err

        except fitbit.exceptions.HTTPBadRequest as err:
            _LOGGER.error("Bad request to Fitbit API: %s", err)
            raise FitbitAPIError(f"Bad request: {err}") from err

        except Exception as err:
            _LOGGER.error("Failed to create Fitbit activity: %s", err)
            raise FitbitAPIError(f"API error: {err}") from err

    async def get_user_profile(self) -> dict[str, Any]:
        """Get Fitbit user profile for validation."""
        await self._ensure_token_valid()

        try:
            profile = await self.hass.async_add_executor_job(self.client.user_profile_get)
            return profile

        except Exception as err:
            _LOGGER.error("Failed to get user profile: %s", err)
            raise FitbitAPIError(f"Failed to get profile: {err}") from err
