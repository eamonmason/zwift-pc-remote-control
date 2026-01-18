#!/bin/bash
# deploy-zwift-launcher-automation.sh
#
# Deploys Zwift launcher keyboard automation to Windows PC
# This fixes the issue where send keys doesn't work via SSH due to session isolation

set -e

PC_IP="${PC_IP:-192.168.1.194}"
PC_USER="${PC_USER:-eamon}"

echo "=== Deploying Zwift Launcher Automation ==="
echo "Target: $PC_USER@$PC_IP"
echo ""

# Step 1: Create PowerShell script locally
echo "Creating PowerShell script..."
cat > /tmp/zwift-launcher-keys.ps1 << 'EOF'
# Automated keyboard input for Zwift launcher
# Handles Tab, Tab, Enter to start Zwift from the launcher window
# Runs in user's interactive session to access GUI windows

# Wait longer for launcher window to fully initialize (increased to 30s)
Write-Host 'Waiting 30 seconds for launcher window to initialize...'
Start-Sleep -Seconds 30

# Find ZwiftLauncher process
$process = Get-Process ZwiftLauncher -ErrorAction SilentlyContinue
if (-not $process) {
    Write-Host 'ERROR: ZwiftLauncher process not found'
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
    Write-Host 'ERROR: Window handle is 0 (launcher window not accessible)'
    exit 1
}

Write-Host "Found launcher window (handle: $hwnd)"

# Restore if minimized
if ([WinAPI]::IsIconic($hwnd)) {
    Write-Host 'Restoring minimized window'
    [WinAPI]::ShowWindow($hwnd, 9)  # SW_RESTORE
    Start-Sleep -Milliseconds 300
}

# Set as foreground window
$activated = [WinAPI]::SetForegroundWindow($hwnd)
Write-Host "Window activation: $activated"
Start-Sleep -Milliseconds 500

# Send keyboard input
Add-Type -AssemblyName System.Windows.Forms
Write-Host "Sending keyboard input: Tab, Tab, Enter"
[System.Windows.Forms.SendKeys]::SendWait('{TAB}')
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('{TAB}')
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')

Write-Host 'Keyboard input sent successfully'
EOF

# Step 2: Copy script to Windows PC
echo "Copying PowerShell script to PC..."
scp /tmp/zwift-launcher-keys.ps1 "$PC_USER@$PC_IP:C:/Users/$PC_USER/zwift-launcher-keys.ps1"

# Step 3: Create scheduled task
echo "Creating scheduled task..."
ssh "$PC_USER@$PC_IP" "schtasks /Create /TN ZwiftLauncherKeys /TR \"powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\\Users\\$PC_USER\\zwift-launcher-keys.ps1\" /SC ONCE /ST 00:00 /RL HIGHEST /F"

# Step 4: Verify deployment
echo ""
echo "=== Verifying Deployment ==="
echo ""
echo "PowerShell script:"
ssh "$PC_USER@$PC_IP" "dir C:\\Users\\$PC_USER\\zwift-launcher-keys.ps1"
echo ""
echo "Scheduled task:"
ssh "$PC_USER@$PC_IP" "schtasks /Query /TN ZwiftLauncherKeys /FO LIST" | head -15

echo ""
echo "✅ Deployment complete!"
echo ""
echo "The automation will now work when you use the API to start Zwift."
echo "To test manually:"
echo "  1. Start Zwift launcher manually on the PC"
echo "  2. Run: ssh $PC_USER@$PC_IP \"schtasks /Run /TN ZwiftLauncherKeys\""
echo "  3. Verify that ZwiftApp starts"
