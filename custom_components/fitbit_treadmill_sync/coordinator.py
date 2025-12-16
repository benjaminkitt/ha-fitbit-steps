"""Coordinator for Fitbit Treadmill Sync integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import EventStateChangedData, async_track_state_change_event

from .api import FitbitAPI, FitbitAPIError, RateLimitError
from .const import (
    CONF_ACTIVITY_TYPE,
    CONF_AUTO_SYNC,
    CONF_DISTANCE_ENTITY,
    CONF_NOTIFICATION_ENABLED,
    CONF_STATUS_ENTITY,
    CONF_STRIDE_LENGTH,
    EVENT_WORKOUT_SYNCED,
    MAX_DISTANCE,
    MAX_HISTORY_SIZE,
    MIN_DISTANCE,
    STATE_POST_WORKOUT,
    STATE_WORKING,
)

_LOGGER = logging.getLogger(__name__)


class FitbitTreadmillCoordinator:
    """Coordinate treadmill state monitoring and Fitbit sync."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: FitbitAPI,
    ) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.entry = entry
        self.api = api

        # State tracking
        self._current_session: dict[str, Any] | None = None
        self._sync_history: list[dict[str, Any]] = []
        self._last_sync_time: datetime | None = None
        self._unsub_listeners: list = []

    async def async_setup(self) -> None:
        """Set up state listeners."""
        status_entity = self.entry.options.get(CONF_STATUS_ENTITY)

        if not status_entity:
            _LOGGER.error("No status entity configured")
            return

        # Listen for status changes
        self._unsub_listeners.append(
            async_track_state_change_event(
                self.hass,
                [status_entity],
                self._async_status_changed,
            )
        )

        _LOGGER.info("Coordinator setup complete, monitoring: %s", status_entity)

    async def async_unload(self) -> None:
        """Unload coordinator and remove listeners."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        _LOGGER.info("Coordinator unloaded")

    @callback
    async def _async_status_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle treadmill status change."""
        new_state = event.data["new_state"]
        old_state = event.data["old_state"]

        if new_state is None or old_state is None:
            return

        _LOGGER.debug(
            "Status changed: %s -> %s",
            old_state.state,
            new_state.state,
        )

        # Start tracking when workout begins
        if old_state.state != STATE_WORKING and new_state.state == STATE_WORKING:
            await self._async_start_session(new_state.last_changed)

        # Sync when workout completes
        elif old_state.state == STATE_WORKING and new_state.state == STATE_POST_WORKOUT:
            # Check if auto-sync is enabled
            if self.entry.data.get(CONF_AUTO_SYNC, True):
                await self._async_complete_session(new_state.last_changed)
            else:
                _LOGGER.info(
                    "Workout completed but auto-sync is disabled. Use manual sync service."
                )

    async def _async_start_session(self, start_time: datetime) -> None:
        """Start tracking a workout session."""
        try:
            distance = await self._get_distance_value()
            self._current_session = {
                "start_time": start_time,
                "start_distance": distance,
            }
            _LOGGER.info(
                "Started tracking workout session at %s (distance: %.2f mi)",
                start_time,
                distance,
            )
        except Exception as err:
            _LOGGER.warning("Failed to start session tracking: %s", err)
            self._current_session = {
                "start_time": start_time,
                "start_distance": 0.0,
            }

    async def _async_complete_session(self, end_time: datetime) -> None:
        """Complete workout session and sync to Fitbit."""
        if self._current_session is None:
            _LOGGER.warning("No active session found, syncing current distance")
            start_time = end_time
            start_distance = 0.0
        else:
            start_time = self._current_session["start_time"]
            start_distance = self._current_session["start_distance"]

        try:
            # Get final distance
            end_distance = await self._get_distance_value()
            workout_distance = end_distance - start_distance

            # Validate distance
            if workout_distance < MIN_DISTANCE:
                _LOGGER.warning(
                    "Workout distance too small (%.3f mi), skipping sync",
                    workout_distance,
                )
                await self._notify_sync_result(
                    success=False,
                    error=f"Distance too small: {workout_distance:.3f} miles",
                )
                self._current_session = None
                return

            if workout_distance > MAX_DISTANCE:
                _LOGGER.error(
                    "Workout distance unreasonably large (%.2f mi), skipping sync",
                    workout_distance,
                )
                await self._notify_sync_result(
                    success=False,
                    error=f"Distance too large: {workout_distance:.2f} miles",
                )
                self._current_session = None
                return

            # Calculate duration
            duration = end_time - start_time
            duration_minutes = max(1, int(duration.total_seconds() / 60))

            _LOGGER.info(
                "Workout completed: %.2f miles in %d minutes",
                workout_distance,
                duration_minutes,
            )

            # Sync to Fitbit
            await self._async_sync_workout(
                distance=workout_distance,
                start_time=start_time,
                duration_minutes=duration_minutes,
            )

        except Exception as err:
            _LOGGER.error("Failed to complete session: %s", err)
            await self._notify_sync_result(success=False, error=str(err))

        finally:
            self._current_session = None

    async def _async_sync_workout(
        self,
        distance: float,
        start_time: datetime,
        duration_minutes: int,
    ) -> dict[str, Any]:
        """Sync workout to Fitbit."""
        try:
            # Get configuration
            activity_type = self.entry.data.get(CONF_ACTIVITY_TYPE, "Walking")
            stride_length = self.entry.data.get(CONF_STRIDE_LENGTH, 2.5)

            # Convert distance to steps
            steps, conversion_method = await self.api.convert_distance_to_steps(
                distance_miles=distance,
                stride_feet=stride_length,
                activity_type=activity_type,
            )

            _LOGGER.info(
                "Creating Fitbit activity: %s, %.2f miles, %d steps (%s)",
                activity_type,
                distance,
                steps,
                conversion_method,
            )

            # Create activity log in Fitbit
            response = await self.api.create_activity_log(
                activity_type=activity_type,
                distance_miles=distance,
                start_time=start_time,
                duration_minutes=duration_minutes,
                steps=steps,
            )

            # Record in history
            sync_record = {
                "timestamp": datetime.now(),
                "distance_miles": distance,
                "steps": steps,
                "duration_minutes": duration_minutes,
                "conversion_method": conversion_method,
                "activity_type": activity_type,
                "success": True,
                "fitbit_log_id": response.get("activityLog", {}).get("logId"),
            }

            self._sync_history.append(sync_record)

            # Keep history size manageable
            if len(self._sync_history) > MAX_HISTORY_SIZE:
                self._sync_history.pop(0)

            self._last_sync_time = datetime.now()

            # Notify user
            await self._notify_sync_result(
                success=True,
                steps=steps,
                distance=distance,
            )

            # Fire event for automations
            self.hass.bus.async_fire(
                EVENT_WORKOUT_SYNCED,
                {
                    "entity_id": self.entry.entry_id,
                    "steps": steps,
                    "distance": distance,
                    "duration_minutes": duration_minutes,
                    "conversion_method": conversion_method,
                },
            )

            _LOGGER.info("Successfully synced workout to Fitbit")

            return sync_record

        except ConfigEntryAuthFailed as err:
            _LOGGER.error("Authentication failed, reauth required: %s", err)
            await self._notify_sync_result(
                success=False,
                error="Authentication failed - please reconfigure integration",
            )
            # Trigger reauth
            self.entry.async_start_reauth(self.hass)
            raise

        except RateLimitError as err:
            _LOGGER.warning("Rate limit exceeded: %s", err)
            await self._notify_sync_result(
                success=False,
                error="Fitbit rate limit exceeded - will retry later",
            )
            # Could implement retry queue here
            raise

        except FitbitAPIError as err:
            _LOGGER.error("Fitbit API error: %s", err)
            await self._notify_sync_result(
                success=False,
                error=f"Fitbit API error: {err}",
            )
            raise

        except Exception as err:
            _LOGGER.error("Unexpected error during sync: %s", err)
            await self._notify_sync_result(
                success=False,
                error=f"Unexpected error: {err}",
            )
            raise

    async def _get_distance_value(self) -> float:
        """Get current distance from sensor."""
        distance_entity = self.entry.options.get(CONF_DISTANCE_ENTITY)

        if not distance_entity:
            raise ValueError("Distance entity not configured")

        state = self.hass.states.get(distance_entity)

        if state is None:
            raise ValueError(f"Distance entity {distance_entity} not found")

        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            raise ValueError(f"Distance entity unavailable: {state.state}")

        try:
            distance = float(state.state)
        except (ValueError, TypeError) as err:
            raise ValueError(f"Invalid distance value: {state.state}") from err

        return distance

    async def _notify_sync_result(
        self,
        success: bool,
        steps: int | None = None,
        distance: float | None = None,
        error: str | None = None,
    ) -> None:
        """Send persistent notification to user."""
        if not self.entry.data.get(CONF_NOTIFICATION_ENABLED, True):
            return

        if success:
            message = (
                f"Treadmill workout synced to Fitbit!\n\n"
                f"Distance: {distance:.2f} miles\n"
                f"Steps: {steps:,}"
            )
            notification_id = f"{self.entry.entry_id}_sync_success"
        else:
            message = f"Failed to sync workout to Fitbit:\n{error}"
            notification_id = f"{self.entry.entry_id}_sync_error"

        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Fitbit Treadmill Sync",
                "message": message,
                "notification_id": notification_id,
            },
        )

    async def manual_sync(self, distance_override: float | None = None) -> dict[str, Any]:
        """Manually trigger workout sync."""
        _LOGGER.info("Manual sync triggered")

        try:
            # Get distance
            if distance_override is not None:
                distance = distance_override
                _LOGGER.info("Using override distance: %.2f miles", distance)
            else:
                distance = await self._get_distance_value()
                _LOGGER.info("Using sensor distance: %.2f miles", distance)

            # Use current time
            start_time = datetime.now(self.hass.config.time_zone)

            # Estimate duration based on distance (assume 20 min/mile average)
            duration_minutes = max(1, int(distance * 20))

            # Perform sync
            return await self._async_sync_workout(
                distance=distance,
                start_time=start_time,
                duration_minutes=duration_minutes,
            )

        except Exception as err:
            _LOGGER.error("Manual sync failed: %s", err)
            await self._notify_sync_result(success=False, error=str(err))
            raise

    @property
    def sync_history(self) -> list[dict[str, Any]]:
        """Get sync history."""
        return self._sync_history

    @property
    def last_sync_time(self) -> datetime | None:
        """Get last sync time."""
        return self._last_sync_time
