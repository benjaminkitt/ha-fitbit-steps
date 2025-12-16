"""Constants for the Fitbit Treadmill Sync integration."""
from typing import Final

DOMAIN: Final = "fitbit_treadmill_sync"

# OAuth2 Configuration
OAUTH2_AUTHORIZE: Final = "https://www.fitbit.com/oauth2/authorize"
OAUTH2_TOKEN: Final = "https://api.fitbit.com/oauth2/token"
OAUTH2_SCOPES: Final = ["activity"]

# Config Entry Keys - OAuth Data
CONF_OAUTH_ACCESS_TOKEN: Final = "access_token"
CONF_OAUTH_REFRESH_TOKEN: Final = "refresh_token"
CONF_OAUTH_EXPIRES_AT: Final = "expires_at"

# Config Entry Keys - User Configuration
CONF_STATUS_ENTITY: Final = "status_entity"
CONF_DISTANCE_ENTITY: Final = "distance_entity"
CONF_ACTIVITY_TYPE: Final = "activity_type"
CONF_STRIDE_LENGTH: Final = "stride_length"
CONF_USER_HEIGHT: Final = "user_height"
CONF_AUTO_SYNC: Final = "auto_sync"
CONF_NOTIFICATION_ENABLED: Final = "notification_enabled"

# Default Values
DEFAULT_ACTIVITY_TYPE: Final = "Walking"
DEFAULT_AUTO_SYNC: Final = True
DEFAULT_NOTIFICATION_ENABLED: Final = True
DEFAULT_STRIDE_MULTIPLIER: Final = 0.413  # For calculating stride from height

# Activity Types and Fitbit IDs
ACTIVITY_TYPES: Final = {
    "Walking": 90013,
    "Running": 90009,
    "Treadmill": 15000,
}

# Fitbit API Configuration
FITBIT_API_BASE: Final = "https://api.fitbit.com"
FITBIT_RATE_LIMIT: Final = 150  # Requests per hour
TOKEN_REFRESH_BUFFER: Final = 300  # Refresh token 5 minutes before expiry

# State Values
STATE_POST_WORKOUT: Final = "Post-Workout"
STATE_WORKING: Final = "Working"
STATE_STANDBY: Final = "Standby"

# Service Names
SERVICE_SYNC_WORKOUT: Final = "sync_workout"

# Events
EVENT_WORKOUT_SYNCED: Final = f"{DOMAIN}_workout_synced"

# Conversion Constants
FEET_PER_MILE: Final = 5280
INCHES_TO_FEET: Final = 12

# Validation Limits
MIN_DISTANCE: Final = 0.01  # miles
MAX_DISTANCE: Final = 100.0  # miles
MIN_STRIDE: Final = 0.5  # feet
MAX_STRIDE: Final = 5.0  # feet
MIN_HEIGHT: Final = 36  # inches (3 feet)
MAX_HEIGHT: Final = 96  # inches (8 feet)

# Sync History
MAX_HISTORY_SIZE: Final = 50
