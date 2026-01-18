# iOS Siri Shortcuts Integration Guide

This guide shows you how to create iOS Siri Shortcuts to control your Zwift PC using voice commands.

## Prerequisites

- iOS device (iPhone or iPad) running iOS 14 or later
- Shortcuts app installed (pre-installed on iOS 14+)
- Zwift Control API running on your local network
- Both iOS device and API server on the same local network

## Finding Your API URL

The API URL depends on where you're running the Zwift Control API:

- **Raspberry Pi**: `http://raspberrypi.local:8000` or `http://192.168.1.X:8000`
- **Mac/Linux**: `http://localhost:8000` (if on same machine) or `http://192.168.1.X:8000`

To find your IP address:

```bash
# On Raspberry Pi/Linux
hostname -I

# On Mac
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Test the API from your iOS device's browser:

```
http://YOUR_IP:8000/health
```

You should see: `{"status":"healthy","timestamp":"..."}`

## Shortcut 1: "Start Zwift"

This shortcut wakes your PC, launches Zwift, and notifies you when ready.

### Steps

1. Open **Shortcuts** app on iOS
2. Tap **+** to create new shortcut
3. Add actions in this order:

#### Action 1: Get Contents of URL

- **URL**: `http://192.168.1.X:8000/api/v1/control/start`
  - Replace `192.168.1.X` with your API IP address
- **Method**: POST
- **Request Body**: (leave empty)

#### Action 2: Get Dictionary Value

- **Get Value for**: `task_id`
- **Dictionary**: Magic Variable (select output from Action 1)
- Tap the result to set variable name: **TaskID**

#### Action 3: Wait

- **Time**: 30 seconds

#### Action 4: Repeat

- **Repeat**: 6 times

#### Inside the Repeat Loop - Action 5: Get Contents of URL

- **URL**: `http://192.168.1.X:8000/api/v1/control/tasks/`
  - After the URL, add Magic Variable: **TaskID**
- **Method**: GET

#### Inside the Repeat Loop - Action 6: Get Dictionary Value

- **Get Value for**: `status`
- **Dictionary**: Magic Variable (select output from Action 5)
- Set variable name: **Status**

#### Inside the Repeat Loop - Action 7: If

- **If**: **Status** is "completed"
- **Then**:
  - Add **Show Notification** action:
    - **Title**: "Zwift is ready!"
    - **Body**: "PC woken and Zwift launched successfully"
  - Add **Exit Shortcut** action
- **Otherwise**: (leave empty)

#### Inside the Repeat Loop - Action 8: If (second condition)

- **If**: **Status** is "failed"
- **Then**:
  - Add **Get Dictionary Value** action:
    - **Get Value for**: `error`
    - **Dictionary**: Magic Variable (select output from Action 5)
  - Add **Show Notification** action:
    - **Title**: "Zwift start failed"
    - **Body**: Magic Variable (error from previous action)
  - Add **Exit Shortcut** action
- **Otherwise**: (leave empty)

#### Inside the Repeat Loop - Action 9: Wait

- **Time**: 30 seconds

#### After the Repeat Loop - Action 10: Show Notification

- **Title**: "Zwift start timed out"
- **Body**: "The start sequence did not complete in time. Check the API or PC."

### Configure Siri Phrase

1. Tap the shortcut name at the top
2. Name it "Start Zwift"
3. Tap "Add to Siri"
4. Record phrase: "Start Zwift" or "Wake up my Zwift PC"

### Usage

Say: "Hey Siri, start Zwift"

Expected behavior:

- Shortcut starts immediately
- After ~30s: notification "Zwift is ready!" (or continues waiting)
- Total time: 2-3 minutes for full sequence

## Shortcut 2: "Stop Zwift"

This shortcut shuts down your Zwift PC.

### Steps

1. Open **Shortcuts** app
2. Tap **+** to create new shortcut
3. Add actions:

#### Action 1: Get Contents of URL

- **URL**: `http://192.168.1.X:8000/api/v1/control/stop`
  - Replace `192.168.1.X` with your API IP address
- **Method**: POST

#### Action 2: Show Notification

- **Title**: "Zwift PC shutting down"
- **Body**: "PC will power off in 5 seconds"

### Configure Siri Phrase

1. Name it "Stop Zwift"
2. Tap "Add to Siri"
3. Record phrase: "Stop Zwift" or "Shut down my Zwift PC"

### Usage

Say: "Hey Siri, stop Zwift"

Expected behavior:

- Immediate notification
- PC shuts down within 5 seconds

## Shortcut 3: "Check Zwift Status"

This shortcut checks if your PC and Zwift are running.

### Steps

1. Open **Shortcuts** app
2. Tap **+** to create new shortcut
3. Add actions:

#### Action 1: Get Contents of URL

- **URL**: `http://192.168.1.X:8000/api/v1/status/full`
- **Method**: GET

#### Action 2: Get Dictionary Value

- **Get Value for**: `pc.online`
- **Dictionary**: Magic Variable (output from Action 1)
- Set variable name: **PCOnline**

#### Action 3: Get Dictionary Value

- **Get Value for**: `zwift.running`
- **Dictionary**: Magic Variable (output from Action 1)
- Set variable name: **ZwiftRunning**

#### Action 4: Text

Build a status message using **Text** action:

```
PC: PCOnline
Zwift: ZwiftRunning
```

(Use Magic Variables for PCOnline and ZwiftRunning)

#### Action 5: Show Notification

- **Title**: "Zwift Status"
- **Body**: Magic Variable (Text from Action 4)

### Configure Siri Phrase

1. Name it "Check Zwift"
2. Tap "Add to Siri"
3. Record phrase: "Check Zwift status" or "Is Zwift running?"

### Usage

Say: "Hey Siri, check Zwift status"

Expected behavior:

- Immediate notification showing:
  - "PC: true, Zwift: true" (if running)
  - "PC: false, Zwift: false" (if offline)

## Shortcut 4: "Wake Zwift PC" (Wake Only)

This shortcut only wakes the PC without launching Zwift.

### Steps

1. Open **Shortcuts** app
2. Tap **+** to create new shortcut
3. Add actions:

#### Action 1: Get Contents of URL

- **URL**: `http://192.168.1.X:8000/api/v1/control/wake`
- **Method**: POST

#### Action 2: Get Dictionary Value

- **Get Value for**: `task_id`
- **Dictionary**: Magic Variable (output from Action 1)
- Set variable name: **TaskID**

#### Action 3: Wait

- **Time**: 30 seconds

#### Action 4: Repeat

- **Repeat**: 3 times

#### Inside Repeat - Action 5: Get Contents of URL

- **URL**: `http://192.168.1.X:8000/api/v1/control/tasks/` + Magic Variable **TaskID**
- **Method**: GET

#### Inside Repeat - Action 6: Get Dictionary Value

- **Get Value for**: `status`
- Set variable name: **Status**

#### Inside Repeat - Action 7: If

- **If**: **Status** is "completed"
- **Then**:
  - **Show Notification**: "PC is awake!"
  - **Exit Shortcut**

#### Inside Repeat - Action 8: Wait

- **Time**: 20 seconds

#### After Repeat - Action 9: Show Notification

- **Title**: "PC wake timed out"
- **Body**: "PC did not respond in time"

### Configure Siri Phrase

1. Name it "Wake Zwift PC"
2. Add Siri phrase: "Wake my PC"

## Advanced: Combined Morning Routine

Create a shortcut that:

1. Starts your coffee maker (if smart home compatible)
2. Wakes and starts Zwift
3. Opens Zwift Companion app

### Steps

1. Create new shortcut named "Morning Ride"
2. Add **Home** action (if you have smart coffee maker)
3. Add **Get Contents of URL** (start Zwift sequence as above)
4. Add **Open App** action → Select "Zwift Companion"
5. Configure Siri: "Start my morning ride"

## Troubleshooting

### "The operation couldn't be completed" Error

**Cause**: iOS cannot reach the API server.

**Solutions**:

1. Verify both devices on same WiFi network
2. Test API URL in Safari: `http://YOUR_IP:8000/health`
3. Check API server is running: `docker-compose logs zwift-api`
4. Verify firewall not blocking port 8000

### "Invalid JSON" or Parsing Error

**Cause**: API returned error or unexpected response.

**Solutions**:

1. Add **Get Contents of URL** output to **Show Result** action to see raw response
2. Check API logs for errors
3. Test endpoint directly in browser or curl

### Shortcut Times Out

**Cause**: PC is slow to boot or network is slow.

**Solutions**:

1. Increase wait times (30s → 45s)
2. Increase repeat count (6 → 8)
3. Check PC wake-on-LAN is working: `ping PC_IP`

### Siri Says "There was a problem with the app"

**Cause**: Shortcut has an error.

**Solutions**:

1. Open Shortcuts app and run manually
2. Check each action for missing Magic Variables
3. Verify URL is correct (no extra spaces or quotes)

## Privacy & Security

- **Local Network Only**: Shortcuts only work when iOS device is on the same network as API
- **No Internet Required**: All communication stays on local network
- **No Authentication**: API has no auth - ensure it's not exposed to internet
- **No Data Collection**: Shortcuts run entirely on your device

## Tips & Best Practices

1. **Test in Shortcuts App First**: Run shortcuts manually before adding to Siri
2. **Use WiFi**: Ensure iOS device is on WiFi (not cellular) for local network access
3. **Descriptive Names**: Use clear names like "Start Zwift" vs "Zwift 1"
4. **Add Confirmation**: Consider adding "Ask Before Running" for destructive actions (shutdown)
5. **Widgets**: Add shortcuts to home screen widget for quick access without Siri
6. **Automation**: Use Shortcuts automation to run at specific times (e.g., 6 AM on weekdays)

## Example Automation: Weekday Morning

1. Open **Shortcuts** → **Automation** tab
2. Tap **+** → **Create Personal Automation**
3. **Time of Day**: 6:00 AM
4. **Repeat**: Select Mon, Tue, Wed, Thu, Fri
5. **Add Action** → **Run Shortcut** → Select "Start Zwift"
6. **Disable** "Ask Before Running"

Now your Zwift PC will automatically wake and launch Zwift every weekday at 6 AM.

## Support

For issues or questions:

1. Check API logs: `docker-compose logs zwift-api`
2. Test endpoints in browser or curl
3. Review [README.md](README.md) for API documentation
4. Check PC is configured correctly per [CLAUDE.md](CLAUDE.md)

## Additional Resources

- [Shortcuts User Guide](https://support.apple.com/guide/shortcuts/welcome/ios)
- [API Documentation](README.md)
- [PC Configuration](CLAUDE.md)
