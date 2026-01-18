# Zwift Launcher Automation

**Date**: 2026-01-18
**Feature**: Automated keyboard input for Zwift launcher

## Problem

The Zwift application has a launcher window that requires manual keyboard interaction to start the main Zwift program:

1. User must press **Tab** twice to navigate to the "Launch" button
2. User must press **Enter** to activate and start Zwift

This breaks the automation flow, as the scheduled task launches the **launcher** but not the actual Zwift application.

## Solution

Added automated keyboard input to activate the Zwift launcher after it starts.

### Implementation

#### New Method: `activate_zwift_launcher()`

**Location**: `api/services/pc_control.py:145-184`

**Functionality**:

- Waits 3 seconds for launcher window to appear
- Sends keyboard input: Tab, Tab, Enter
- Uses PowerShell `WScript.Shell` COM object for reliable key sending

**Code**:

```python
async def activate_zwift_launcher(self) -> bool:
    """
    Send keyboard input to Zwift launcher (Tab, Tab, Enter).

    After the Zwift launcher opens, it requires keyboard interaction
    to actually start the main Zwift application:
    - Press Tab twice to navigate to the Launch button
    - Press Enter to activate it

    Returns:
        True if keyboard input was sent successfully
    """
    logger.info("Activating Zwift launcher (Tab, Tab, Enter)...")
    try:
        # PowerShell script to send keyboard input
        script = """
            # Wait for launcher window to appear
            Start-Sleep -Seconds 3

            # Send Tab, Tab, Enter using WScript.Shell
            $wshell = New-Object -ComObject wscript.shell
            $wshell.SendKeys('{TAB}')
            Start-Sleep -Milliseconds 500
            $wshell.SendKeys('{TAB}')
            Start-Sleep -Milliseconds 500
            $wshell.SendKeys('~')  # ~ is Enter key

            Write-Host 'Keyboard input sent to launcher'
        """
        stdout, stderr, return_code = await self.ssh.execute_powershell(script, timeout=15)
        if return_code == 0:
            logger.info("Zwift launcher activated successfully")
            return True
        else:
            logger.warning(f"Failed to activate launcher: {stderr}")
            return False
    except Exception as e:
        logger.warning(f"Error activating Zwift launcher: {e}")
        # Not critical - Zwift might launch anyway
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

## Technical Details

### Why WScript.Shell?

PowerShell has two methods for sending keyboard input:

1. **System.Windows.Forms.SendKeys** - Requires loading Windows Forms assembly
2. **WScript.Shell.SendKeys** - COM object, more reliable for background windows

We chose `WScript.Shell` because:

- Works reliably with background/hidden windows
- No assembly loading required
- Well-established COM interface

### Key Codes

- `{TAB}` - Tab key
- `~` - Enter key (tilde represents Enter in WScript.Shell)
- `{ENTER}` - Also works, but `~` is shorter

### Timing

- **3 second wait**: Allows launcher window to fully appear
- **500ms between keys**: Ensures UI has time to respond to Tab navigation
- **15 second timeout**: Prevents hanging if something goes wrong

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
