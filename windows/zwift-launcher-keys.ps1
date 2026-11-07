# Automated keyboard input for Zwift launcher
# Handles Tab, Tab, Enter to start Zwift from the launcher window
# Runs in user's interactive session to access GUI windows
#
# Exit codes (visible as LastTaskResult on the ZwiftLauncherKeys task):
#   0  Zwift is running (keys worked, or it was already running)
#   2  no ZwiftLauncher process appeared
#   3  the launcher is running but never showed a window
#   4  keys were sent but ZwiftApp did not start
#
# Process.MainWindowHandle is 0 while the launcher has no visible window (for
# example an autostarted "SilentLaunch" instance, or one still starting up), and
# is cached on the Process object, so we re-read the processes on every pass.
#
# The launcher UI is a WebView2 page. After a fast cold boot its window exists
# several seconds before the page's buttons do, so the first Tab/Tab/Enter can
# land on nothing (observed: the same keys start Zwift fine once the page has
# loaded). A run therefore makes up to $maxAttempts attempts:
#   1. send the keys;
#   2. send them again after a longer settle, on the same launcher;
#   3. close the launcher and start a fresh one (covers a page that failed to
#      load, e.g. "WebView2 navigation failed: ConnectionAborted" before the
#      network was up), with the longest settle.
# It cannot get past a sign-in screen: if the launcher has lost its saved login
# every attempt fails and the exit code is 4.
#
# Starting ZwiftLauncher.exe again surfaces a window on the already-running
# instance (observed: same process id before and after), but we do not rely on
# it being single-instance, so we start the launcher at most ONCE per run, never
# in a loop.

$launcherPath = 'C:\Program Files (x86)\Zwift\ZwiftLauncher.exe'
$windowTimeoutSeconds = 40
$reinvokeAfterSeconds = 12
$zwiftStartTimeoutSeconds = 20
$maxAttempts = 3
$logPath = Join-Path $env:USERPROFILE 'zwift-launcher-keys.log'

try { Start-Transcript -Path $logPath -Force | Out-Null } catch { }

# A second /start, or a manual launch, must not be undone by stray keystrokes.
if (Get-Process ZwiftApp -ErrorAction SilentlyContinue) {
    Write-Host 'ZwiftApp is already running; nothing to do'
    exit 0
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

Add-Type -AssemblyName System.Windows.Forms

# One attempt: find the launcher window, let it settle, send the keys, and
# confirm ZwiftApp started. Returns the script's exit code for this attempt.
function Invoke-LauncherAttempt([int]$attempt) {
    # A slow start from the previous attempt's keys must not get stray ones.
    if (Get-Process ZwiftApp -ErrorAction SilentlyContinue) {
        Write-Host 'ZwiftApp is running'
        return 0
    }

    $start = Get-Date
    $deadline = $start.AddSeconds($windowTimeoutSeconds)
    $invoked = $false
    $sawProcess = $false
    $hwnd = [IntPtr]::Zero

    while ((Get-Date) -lt $deadline) {
        foreach ($p in Get-Process ZwiftLauncher -ErrorAction SilentlyContinue) {
            $sawProcess = $true
            if ($p.MainWindowHandle -ne 0) { $hwnd = $p.MainWindowHandle; break }
        }
        if ($hwnd -ne [IntPtr]::Zero) { break }

        # No window yet. If nothing is running, or a normal launch has had time
        # to draw and still has no window, start the launcher once.
        $waited = ((Get-Date) - $start).TotalSeconds
        if (-not $invoked -and (-not $sawProcess -or $waited -ge $reinvokeAfterSeconds)) {
            Write-Host 'No launcher window; invoking the launcher once'
            Start-Process $launcherPath -WindowStyle Maximized
            $invoked = $true
        }
        Start-Sleep -Seconds 1
    }

    if ($hwnd -eq [IntPtr]::Zero) {
        if ($sawProcess) {
            Write-Host "ERROR: ZwiftLauncher is running but showed no window within $windowTimeoutSeconds s"
            return 3
        }
        Write-Host "ERROR: ZwiftLauncher process not found within $windowTimeoutSeconds s"
        return 2
    }

    Write-Host "Found launcher window (handle: $hwnd)"

    # The window can exist before its page has loaded; give the UI time to
    # settle, longer on each retry.
    Start-Sleep -Seconds (3 + 5 * ($attempt - 1))

    # Restore if minimized
    if ([WinAPI]::IsIconic($hwnd)) {
        Write-Host 'Restoring minimized window'
        [WinAPI]::ShowWindow($hwnd, 9) | Out-Null  # SW_RESTORE
        Start-Sleep -Milliseconds 300
    }

    # Set as foreground window
    $activated = [WinAPI]::SetForegroundWindow($hwnd)
    Write-Host "Window activation: $activated"
    Start-Sleep -Milliseconds 500

    Write-Host "Sending keyboard input: Tab, Tab, Enter"
    [System.Windows.Forms.SendKeys]::SendWait('{TAB}')
    Start-Sleep -Milliseconds 500
    [System.Windows.Forms.SendKeys]::SendWait('{TAB}')
    Start-Sleep -Milliseconds 500
    [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
    Write-Host 'Keyboard input sent'

    # Do not report success on keystrokes alone: confirm the game really started.
    $zwiftDeadline = (Get-Date).AddSeconds($zwiftStartTimeoutSeconds)
    while ((Get-Date) -lt $zwiftDeadline) {
        if (Get-Process ZwiftApp -ErrorAction SilentlyContinue) {
            Write-Host 'ZwiftApp started'
            return 0
        }
        Start-Sleep -Seconds 1
    }

    Write-Host "ERROR: keys were sent but ZwiftApp did not start within $zwiftStartTimeoutSeconds s"
    return 4
}

$exitCode = 1
for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    Write-Host "--- Attempt $attempt of $maxAttempts"
    $exitCode = Invoke-LauncherAttempt $attempt
    if ($exitCode -eq 0) { break }

    # Only the last attempt gets a brand-new launcher; earlier ones reuse the
    # running one, which will usually have finished loading by now.
    if ($attempt -eq ($maxAttempts - 1)) {
        Write-Host 'Closing the launcher so the next attempt starts a fresh one'
        Get-Process ZwiftLauncher -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 5
    }
}

try { Stop-Transcript | Out-Null } catch { }
exit $exitCode
