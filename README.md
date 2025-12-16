# Fitbit Treadmill Sync for Home Assistant

Automatically sync your treadmill workouts to Fitbit! This custom integration monitors your treadmill sensors in Home Assistant and creates activity logs in Fitbit when you complete a workout.

## Features

- 🏃 **Automatic Sync**: Detects when your treadmill workout completes and syncs to Fitbit
- 🔐 **Secure OAuth 2.0**: Full OAuth authentication through Home Assistant UI
- 📊 **Smart Step Conversion**: Converts distance to steps using your stride length or height
- ⚙️ **Configurable**: Choose activity type (Walking/Running/Treadmill) and sync preferences
- 🔔 **Notifications**: Get notified when workouts sync successfully
- 🛠️ **Manual Sync**: Service available for manual workout syncing
- 🔄 **Auto Token Refresh**: OAuth tokens refresh automatically

## Prerequisites

### 1. Home Assistant
- Home Assistant 2024.1.0 or later
- A treadmill integrated with Home Assistant (e.g., Walking Pad via Bluetooth)

### 2. Treadmill Sensors
You need two sensors from your treadmill:
- **Status Sensor**: Changes to `Post-Workout` when workout completes
- **Distance Sensor**: Reports workout distance in miles

### 3. Fitbit Developer Application
You'll need to create a Fitbit OAuth application:

1. Go to https://dev.fitbit.com/apps/new
2. Fill in the application details:
   - **Application Name**: Home Assistant Treadmill Sync (or your choice)
   - **Description**: Sync treadmill workouts to Fitbit
   - **Application Website**: Your Home Assistant URL
   - **Organization**: Personal or your name
   - **Organization Website**: Your Home Assistant URL
   - **OAuth 2.0 Application Type**: Personal
   - **Callback URL**: `{YOUR_HA_URL}/auth/external/callback`
     - Replace `{YOUR_HA_URL}` with your Home Assistant URL (e.g., `https://homeassistant.local:8123`)
     - Must use the exact URL you access Home Assistant with
   - **Default Access Type**: Read & Write
3. Click "Register"
4. Copy your **OAuth 2.0 Client ID** and **Client Secret** - you'll need these

## Installation

### Option 1: HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/benjaminkitt/ha-fitbit-steps`
6. Select "Integration" as the category
7. Click "Add"
8. Find "Fitbit Treadmill Sync" in HACS and click "Download"
9. Restart Home Assistant

### Option 2: Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/fitbit_treadmill_sync` folder to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

### Step 1: Add Application Credentials

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click on **Application Credentials** (in the top right menu)
3. Click **Add Application Credential**
4. Select **Fitbit** from the dropdown
5. Enter your Fitbit OAuth 2.0 **Client ID** and **Client Secret**
6. Click **Add**

### Step 2: Add Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Fitbit Treadmill Sync"
4. Click to start setup

### Step 3: Authorize with Fitbit

1. Click **Authorize** to connect to Fitbit
2. You'll be redirected to Fitbit's website
3. Log in to your Fitbit account
4. Click **Allow** to grant access
5. You'll be redirected back to Home Assistant

### Step 4: Select Treadmill Entities

1. **Status Entity**: Select the sensor that changes to "Post-Workout"
   - Example: `sensor.walking_pad_status`
2. **Distance Entity**: Select the sensor showing distance in miles
   - Example: `sensor.walking_pad_distance_total`
3. Click **Submit**

### Step 5: Configure Step Conversion

1. **Activity Type**: Choose Walking, Running, or Treadmill
2. **Stride Length** OR **Height**:
   - Either enter your stride length in feet
   - Or enter your height in inches (stride will be calculated)
3. **Auto Sync**: Enable to automatically sync workouts (recommended)
4. **Notifications**: Enable to receive sync notifications
5. Click **Submit**

Setup complete! 🎉

## Usage

### Automatic Sync

When enabled (default), the integration automatically:
1. Detects when your treadmill status changes to "Post-Workout"
2. Reads the workout distance
3. Converts distance to steps
4. Creates an activity log in Fitbit
5. Sends you a notification with the results

### Manual Sync

You can manually trigger a sync using the service:

```yaml
service: fitbit_treadmill_sync.sync_workout
data:
  distance: 2.5  # Optional: override distance in miles
```

**Service Parameters:**
- `distance` (optional): Override the distance value from the sensor

### Using in Automations

You can create automations based on successful syncs:

```yaml
automation:
  - alias: "Celebrate Workout Sync"
    trigger:
      - platform: event
        event_type: fitbit_treadmill_sync_workout_synced
    action:
      - service: notify.mobile_app
        data:
          message: "Great workout! {{ trigger.event.data.steps }} steps synced to Fitbit!"
```

**Event Data:**
- `entity_id`: Integration entry ID
- `steps`: Number of steps synced
- `distance`: Distance in miles
- `duration_minutes`: Workout duration
- `conversion_method`: How steps were calculated

## Configuration Options

You can reconfigure the integration at any time:

1. Go to **Settings** → **Devices & Services**
2. Find **Fitbit Treadmill Sync**
3. Click **Configure**

### Available Options

- **Status Entity**: The sensor monitoring treadmill status
- **Distance Entity**: The sensor showing workout distance
- **Activity Type**: Walking, Running, or Treadmill
- **Stride Length**: Your stride in feet
- **Height**: Your height in inches (alternative to stride)
- **Auto Sync**: Automatically sync when workout completes
- **Notifications**: Show persistent notifications

## Troubleshooting

### "Entity not found" Error

**Problem**: The integration can't find your treadmill sensors.

**Solution**:
- Verify your treadmill is connected to Home Assistant
- Check the entity IDs match exactly (case-sensitive)
- Ensure sensors are available (not unavailable or unknown)

### "Authentication Failed" Error

**Problem**: OAuth authentication isn't working.

**Solution**:
- Verify your Fitbit OAuth app is configured correctly
- Check the Callback URL matches your Home Assistant URL exactly
- Ensure Application Credentials are added correctly
- Try removing and re-adding the integration

### Workouts Not Syncing

**Problem**: Workouts complete but don't sync to Fitbit.

**Solutions**:
1. Check that **Auto Sync** is enabled in configuration
2. Verify the status sensor changes to exactly "Post-Workout"
3. Check Home Assistant logs for errors:
   ```
   Settings → System → Logs
   Search for: fitbit_treadmill_sync
   ```
4. Ensure distance is within valid range (0.01 - 100 miles)

### Rate Limit Errors

**Problem**: "Rate limit exceeded" errors in logs.

**Solution**:
- Fitbit allows 150 API requests per hour
- This is unlikely with normal use (1-5 workouts/day)
- Wait an hour and try again
- Consider disabling auto-sync if testing frequently

### Steps Seem Inaccurate

**Problem**: Step count doesn't match expected value.

**Solutions**:
- Measure your actual stride length and update configuration
- Or update your height for automatic stride calculation
- Remember: stride varies between walking and running
- Consider adjusting activity type if needed

### Token Expired

**Problem**: "Token expired" or "Reauth required" messages.

**Solution**:
- Go to **Settings** → **Devices & Services**
- Click on **Fitbit Treadmill Sync**
- Click **Reauthenticate**
- Follow the OAuth flow again

## FAQ

### Q: Can I sync multiple treadmills?

A: Currently, each integration instance supports one treadmill. To sync multiple treadmills, add the integration multiple times with different entity selections.

### Q: Does this work with other fitness equipment?

A: Yes! As long as your equipment has sensors for status and distance in Home Assistant, you can use this integration. Just select the appropriate sensors during setup.

### Q: What happens if my internet is down?

A: Syncs will fail, but you'll receive an error notification. Currently, there's no automatic retry queue, but you can use the manual sync service once internet is restored.

### Q: How accurate is the step conversion?

A: The manual calculation uses the standard formula: `steps = (distance_miles × 5280) / stride_feet`. Accuracy depends on your stride length. For best results, measure your actual stride and update the configuration.

### Q: Can I change the activity type for past workouts?

A: No, once a workout is synced to Fitbit, you'll need to edit it directly in the Fitbit app if you want to change the activity type.

### Q: Will this drain my Fitbit API quota?

A: No. Fitbit allows 150 requests per hour. Even with 5 workouts per day, you'll only use about 5-10 requests total, well below the limit.

### Q: Does this work with Fitbit's new API?

A: This integration uses Fitbit's Web API v1.2, which is their current stable API for creating activity logs.

## Technical Details

### Architecture

- **OAuth 2.0**: Secure authentication using Home Assistant's Application Credentials
- **State Monitoring**: Uses `async_track_state_change_event` for efficient state tracking
- **Token Management**: Automatic token refresh with 5-minute buffer
- **Error Handling**: Graceful degradation with user notifications
- **Rate Limiting**: Built-in protection against API rate limits

### Data Privacy

- All OAuth tokens are stored encrypted in Home Assistant
- Only the "activity" scope is requested (no access to profile, weight, etc.)
- No data is stored or transmitted outside Home Assistant and Fitbit
- Sync history is kept locally (last 50 workouts)

### Dependencies

- `fitbit==0.3.1`: Official Fitbit Python library
- `oauthlib==3.2.2`: OAuth 2.0 framework

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

### Development Setup

1. Clone the repository
2. Create a development environment
3. Install dependencies: `pip install fitbit oauthlib`
4. Make your changes
5. Test with a real Home Assistant instance
6. Submit a pull request

## Support

- **Issues**: https://github.com/benjaminkitt/ha-fitbit-steps/issues
- **Discussions**: https://github.com/benjaminkitt/ha-fitbit-steps/discussions

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built for Home Assistant
- Uses the official Fitbit Web API
- Inspired by the need to track treadmill workouts seamlessly

## Changelog

### Version 1.0.0 (2024-12-16)

- Initial release
- OAuth 2.0 authentication
- Automatic workout detection and sync
- Manual sync service
- Configurable activity types and step conversion
- Persistent notifications
- Options flow for reconfiguration
- Event firing for automations
