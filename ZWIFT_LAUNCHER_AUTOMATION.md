# Zwift Launcher Automation

**Date**: 2026-01-18
**Feature**: Automated keyboard input for Zwift launcher
**Latest Update**: 2026-01-18 - Timing fix applied (2s → 30s wait)

## Problem

The Zwift application has a launcher window that requires manual keyboard interaction to start the main Zwift program:

1. User must press **Tab** twice to navigate to the "Launch" button
2. User must press **Enter** to activate and start Zwift

This breaks the automation flow, as the scheduled task launches the **launcher** but not the actual Zwift application.

## Challenge: Windows Session Isolation

Sending keyboard input via SSH doesn't work because of Windows session isolation:

- SSH runs in **Session 0** (services/non-interactive session)
- User desktop runs in **Session 1** (interactive session)
- Processes in Session 0 cannot access windows in Session 1
- `MainWindowHandle` returns `0` when queried from SSH

## Solution

Uses a **scheduled task** that runs in the user's interactive session to send keyboard input. This solves the session isolation problem by running the automation script in the same session as the Zwift launcher window.

### Implementation

#### Component 1: PowerShell Script (`zwift-launcher-keys.ps1`)

**Location**: `C:\Users\eamon\zwift-launcher-keys.ps1` (on Windows PC)

**Functionality**:

- Finds the ZwiftLauncher process
- Gets the window handle
- Sets the window as foreground using Windows API
- Sends keyboard input: Tab, Tab, Enter
- Uses `System.Windows.Forms.SendKeys` for reliable input

**Key Features**:

- Uses Windows API (`SetForegroundWindow`, `ShowWindow`) for window activation
- Handles minimized windows by restoring them first
- Runs in user's interactive session (Session 1) where launcher window is visible

#### Component 2: Scheduled Task (`ZwiftLauncherKeys`)

**Task Name**: `ZwiftLauncherKeys`

**Configuration**:

- **Trigger**: Manual (triggered via API)
- **Action**: Run PowerShell script with `-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass`
- **User**: Current user (eamon)
- **Logon Type**: Interactive (runs in user session, not background)
- **Run Level**: Highest (Administrator privileges)

**Why a Scheduled Task?**

Scheduled tasks configured with `Interactive` logon type run in the user's desktop session (Session 1), giving them access to GUI windows. This bypasses the SSH session isolation issue.

#### Component 3: Python Method (`activate_zwift_launcher()`)

**Location**: `api/services/pc_control.py:179-214`

**Functionality**:

- Triggers the `ZwiftLauncherKeys` scheduled task via SSH
- Waits 3 seconds for keyboard input to complete
- Returns success/failure status

**Code**:

```python
async def activate_zwift_launcher(self) -> bool:
    """
    Send keyboard input to Zwift launcher (Tab, Tab, Enter).

    Uses a scheduled task to run in the user's interactive session,
    which is necessary due to Windows session isolation (SSH runs in
    Session 0, user desktop is in Session 1).

    Returns:
        True if keyboard input was sent successfully
    """
    logger.info("Activating Zwift launcher via scheduled task...")
    try:
        command = f'schtasks /Run /TN "{settings.zwift_launcher_keys_task}"'
        stdout, stderr, return_code = await self.ssh.execute(command, timeout=10)

        if return_code == 0:
            logger.info("Launcher activation task triggered")
            await asyncio.sleep(3)  # Wait for keys to be sent
            return True
        else:
            logger.warning(f"Failed to trigger launcher activation: {stderr}")
            return False
    except Exception as e:
        logger.warning(f"Error activating Zwift launcher: {e}")
        return False
```

#### Updated Sequence

**Location**: `api/services/task_manager.py:151-160`

The start sequence now includes:

```
Step 6:  Launch Zwift application (scheduled task)
Step 6b: Activate Zwift launcher (Tab, Tab, Enter) ← NEW
Step 7:  Launch Sauce for Zwift
Step 8:  Wait for Zwift to start
Step 9:  Set process priorities
```

## Deployment

### Automated Setup Script

Create and run this script from your Mac to deploy the automation:

```bash
#!/bin/bash
# deploy-zwift-launcher-automation.sh

echo "=== Deploying Zwift Launcher Automation ==="

# Step 1: Create PowerShell script locally
cat > /tmp/zwift-launcher-keys.ps1 << 'EOF'
# Wait for launcher window
Start-Sleep -Seconds 2

# Find ZwiftLauncher process
$process = Get-Process ZwiftLauncher -ErrorAction SilentlyContinue
if (-not $process) {
    Write-Host 'ZwiftLauncher not found'
    exit 1
}

# Windows API for window activation
Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class WinAPI {
        [DllImport("user32.dll")]
        public static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        public static extern bool IsIconic(IntPtr hWnd);
    }
"@

# Get window handle
$hwnd = $process.MainWindowHandle
if ($hwnd -eq 0) {
    Write-Host 'Window handle is 0'
    exit 1
}

# Restore if minimized
if ([WinAPI]::IsIconic($hwnd)) {
    [WinAPI]::ShowWindow($hwnd, 9)
    Start-Sleep -Milliseconds 300
}

# Set foreground
[WinAPI]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 500

# Send keys
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait('{TAB}')
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('{TAB}')
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')

Write-Host 'Keys sent successfully'
EOF

# Step 2: Copy script to Windows PC
echo "Copying PowerShell script to PC..."
scp /tmp/zwift-launcher-keys.ps1 eamon@192.168.1.194:C:/Users/eamon/zwift-launcher-keys.ps1

# Step 3: Create scheduled task
echo "Creating scheduled task..."
ssh eamon@192.168.1.194 "schtasks /Create /TN ZwiftLauncherKeys /TR \"powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\\Users\\eamon\\zwift-launcher-keys.ps1\" /SC ONCE /ST 00:00 /RL HIGHEST /F"

# Step 4: Verify deployment
echo ""
echo "=== Verifying Deployment ==="
ssh eamon@192.168.1.194 "dir C:\\Users\\eamon\\zwift-launcher-keys.ps1"
ssh eamon@192.168.1.194 "schtasks /Query /TN ZwiftLauncherKeys /FO LIST"

echo ""
echo "✅ Deployment complete!"
```

### Manual Setup (if needed)

If the automated script doesn't work, manually set up on the Windows PC:

1. **Create PowerShell script** at `C:\Users\eamon\zwift-launcher-keys.ps1` with the content shown above

2. **Create scheduled task**:

   ```powershell
   schtasks /Create /TN ZwiftLauncherKeys /TR "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\Users\eamon\zwift-launcher-keys.ps1" /SC ONCE /ST 00:00 /RL HIGHEST
   ```

3. **Test the task**:

   ```powershell
   # Start Zwift launcher manually first
   schtasks /Run /TN ZwiftLauncherKeys
   ```

## Technical Details

### Why Scheduled Task + Interactive Session?

The key insight is Windows session isolation:

- **Session 0**: Services and SSH connections (non-interactive)
- **Session 1**: User's desktop (interactive)

GUI windows only exist in Session 1, so:

- Scripts run via SSH cannot access GUI windows (MainWindowHandle = 0)
- Scheduled tasks with `Interactive` logon type run in Session 1
- This gives them access to GUI windows for automation

### Why System.Windows.Forms.SendKeys?

PowerShell has two methods for sending keyboard input:

1. **System.Windows.Forms.SendKeys** - .NET assembly, reliable with foreground windows
2. **WScript.Shell.SendKeys** - COM object, less reliable with focus

We use `System.Windows.Forms.SendKeys` because:

- More reliable when window has proper focus
- Consistent behavior with Windows Forms applications
- Better error handling

### Key Codes

- `{TAB}` - Tab key
- `~` - Enter key (tilde represents Enter in WScript.Shell)
- `{ENTER}` - Also works, but `~` is shorter

### Timing

- **30 second wait**: Allows launcher window to fully initialize (increased from 2s on 2026-01-18)
- **500ms between keys**: Ensures UI has time to respond to Tab navigation
- **Total sequence**: ~33 seconds from launch to keyboard input (3s API delay + 30s script wait)

## Testing

### Manual Test

1. Start the Zwift launcher manually
2. Run the keyboard script via SSH:

```bash
ssh eamon@192.168.1.194 "powershell -command \"\$wshell = New-Object -ComObject wscript.shell; Start-Sleep -Seconds 3; \$wshell.SendKeys('{TAB}'); Start-Sleep -Milliseconds 500; \$wshell.SendKeys('{TAB}'); Start-Sleep -Milliseconds 500; \$wshell.SendKeys('~')\""
```

3. Verify Zwift main application launches

### Integration Test

Run the full `/start` endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/control/start
# Monitor task progress
curl http://localhost:8000/api/v1/control/tasks/{TASK_ID}
```

Expected sequence:

```
✅ Step 6:  Launching Zwift application
✅ Step 6b: Activating Zwift launcher
✅ Step 7:  Launching Sauce for Zwift
✅ Step 8:  Waiting for Zwift to start (ZwiftApp.exe process detected)
✅ Step 9:  Setting process priorities
```

## Troubleshooting

### Issue: Keyboard input not working

**Possible causes**:

1. Launcher window doesn't have focus
2. Timing too short (launcher not ready)
3. Different launcher UI layout

**Solutions**:

1. Increase wait time from 3 to 5 seconds
2. Add retry logic
3. Verify launcher UI hasn't changed (Tab, Tab, Enter is still correct)

### Issue: Wrong button activated

If the launcher UI changes, you may need to adjust the Tab count:

- 1 Tab = different button
- 3 Tabs = different button
- Shift+Tab = navigate backwards

### Issue: PowerShell error

Check PowerShell execution policy:

```powershell
Get-ExecutionPolicy
# Should be RemoteSigned or Unrestricted
```

## Alternative Approaches Considered

### 1. Mouse Automation

**Pros**: More precise, clicks exact coordinates
**Cons**: Brittle (breaks if window moves), requires screen resolution detection

### 2. UI Automation Framework

**Pros**: Robust, finds controls by name/type
**Cons**: Complex, requires .NET assemblies, slower

### 3. AutoHotkey

**Pros**: Powerful scripting language for automation
**Cons**: Requires installation of additional software

### 4. Keyboard Input (Chosen)

**Pros**: Simple, reliable, no dependencies
**Cons**: Assumes consistent UI layout

## Future Enhancements

1. **Configurable key sequence** - Allow customization via environment variable
2. **Retry logic** - If Zwift process not detected, retry keyboard input
3. **Window focus verification** - Ensure launcher has focus before sending keys
4. **Adaptive timing** - Adjust wait time based on PC performance

## Files Modified

```
pc-remote-control/
├── api/services/pc_control.py        # Added activate_zwift_launcher()
├── api/services/task_manager.py      # Added step 6b to sequence
├── api/routers/control.py            # Updated endpoint documentation
└── ZWIFT_LAUNCHER_AUTOMATION.md      # This document
```

## References

- [WScript.Shell.SendKeys Documentation](https://ss64.com/vb/sendkeys.html)
- [PowerShell COM Objects](https://docs.microsoft.com/en-us/powershell/scripting/samples/working-with-wmi-objects)
- Zwift launcher behavior (observed 2026-01-18)

---

**Status**: ✅ Implemented
**Tested**: Pending full integration test
**Impact**: Enables fully automated Zwift startup without manual intervention
