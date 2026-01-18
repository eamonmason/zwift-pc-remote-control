#!/bin/bash
# deploy-all-automation.sh
#
# Comprehensive deployment script for all Zwift PC automation
# Sets up scheduled tasks and PowerShell scripts on Windows PC

set -e

PC_IP="${PC_IP:-192.168.1.194}"
PC_USER="${PC_USER:-eamon}"

echo "=========================================="
echo "  Zwift PC Automation - Full Deployment"
echo "=========================================="
echo "Target: $PC_USER@$PC_IP"
echo ""

# Create temp directory for scripts
TEMP_DIR="/tmp/zwift-automation-$$"
mkdir -p "$TEMP_DIR"
trap "rm -rf $TEMP_DIR" EXIT

echo "Creating PowerShell scripts..."

# =============================================================================
# Script 1: LaunchZwift.ps1
# =============================================================================
cat > "$TEMP_DIR/LaunchZwift.ps1" << 'EOF'
# Launch Zwift Launcher
# Updated: 2026-01-18 - Now relies on separate ZwiftLauncherKeys task for automation

# Start ZwiftLauncher
$zwiftPath = "C:\Program Files (x86)\Zwift\ZwiftLauncher.exe"

if (-not (Test-Path $zwiftPath)) {
    Write-Host "ERROR: Zwift not found at $zwiftPath"
    exit 1
}

Write-Host "Launching Zwift..."
Start-Process $zwiftPath -WindowStyle Maximized

Write-Host "Zwift launcher started"
Write-Host "Note: Automation handled by ZwiftLauncherKeys task"
EOF

# =============================================================================
# Script 2: LaunchSauce.ps1
# =============================================================================
cat > "$TEMP_DIR/LaunchSauce.ps1" << 'EOF'
# Launch Sauce for Zwift (handles trademark symbol in filename)

$sauceDir = "C:\Users\eamon\AppData\Local\Programs\sauce4zwift\"

if (-not (Test-Path $sauceDir)) {
    Write-Host "ERROR: Sauce directory not found at $sauceDir"
    exit 1
}

$sauceExe = Get-ChildItem $sauceDir |
    Where-Object { $_.Name -like 'Sauce*' -and $_.Name -notlike 'Uninstall*' } |
    Select-Object -First 1

if ($sauceExe) {
    Start-Process $sauceExe.FullName
    Write-Host "Launched: $($sauceExe.Name)"
} else {
    Write-Host "ERROR: Sauce executable not found in $sauceDir"
    exit 1
}
EOF

# =============================================================================
# Script 3: zwift-launcher-keys.ps1
# =============================================================================
cat > "$TEMP_DIR/zwift-launcher-keys.ps1" << 'EOF'
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

echo "  ✓ Created 3 PowerShell scripts"
echo ""

# =============================================================================
# Deploy Scripts to Windows PC
# =============================================================================
echo "Deploying scripts to Windows PC..."

# Create C:\tools directory if it doesn't exist
ssh "$PC_USER@$PC_IP" "if not exist C:\\tools mkdir C:\\tools" 2>/dev/null || true

# Copy scripts
echo "  → LaunchZwift.ps1"
scp "$TEMP_DIR/LaunchZwift.ps1" "$PC_USER@$PC_IP:C:/tools/LaunchZwift.ps1" > /dev/null 2>&1

echo "  → LaunchSauce.ps1"
scp "$TEMP_DIR/LaunchSauce.ps1" "$PC_USER@$PC_IP:C:/tools/LaunchSauce.ps1" > /dev/null 2>&1

echo "  → zwift-launcher-keys.ps1"
scp "$TEMP_DIR/zwift-launcher-keys.ps1" "$PC_USER@$PC_IP:C:/Users/$PC_USER/zwift-launcher-keys.ps1" > /dev/null 2>&1

echo "  ✓ Scripts deployed"
echo ""

# =============================================================================
# Create Scheduled Tasks
# =============================================================================
echo "Creating scheduled tasks..."

# Task 1: LaunchZwiftRemote
echo "  → LaunchZwiftRemote"
ssh "$PC_USER@$PC_IP" "schtasks /Create /TN LaunchZwiftRemote /TR \"powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\\tools\\LaunchZwift.ps1\" /SC ONCE /ST 00:00 /RL HIGHEST /F" > /dev/null

# Task 2: LaunchSauceRemote
echo "  → LaunchSauceRemote"
ssh "$PC_USER@$PC_IP" "schtasks /Create /TN LaunchSauceRemote /TR \"powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\\tools\\LaunchSauce.ps1\" /SC ONCE /ST 00:00 /RL HIGHEST /F" > /dev/null

# Task 3: ZwiftLauncherKeys
echo "  → ZwiftLauncherKeys"
ssh "$PC_USER@$PC_IP" "schtasks /Create /TN ZwiftLauncherKeys /TR \"powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\\Users\\$PC_USER\\zwift-launcher-keys.ps1\" /SC ONCE /ST 00:00 /RL HIGHEST /F" > /dev/null

echo "  ✓ Scheduled tasks created"
echo ""

# =============================================================================
# Verify Deployment
# =============================================================================
echo "=========================================="
echo "  Verification"
echo "=========================================="
echo ""

echo "PowerShell Scripts:"
ssh "$PC_USER@$PC_IP" "dir C:\\tools\\LaunchZwift.ps1 2>nul && echo   ✓ C:\\tools\\LaunchZwift.ps1 || echo   ✗ Missing: LaunchZwift.ps1"
ssh "$PC_USER@$PC_IP" "dir C:\\tools\\LaunchSauce.ps1 2>nul && echo   ✓ C:\\tools\\LaunchSauce.ps1 || echo   ✗ Missing: LaunchSauce.ps1"
ssh "$PC_USER@$PC_IP" "dir C:\\Users\\$PC_USER\\zwift-launcher-keys.ps1 2>nul && echo   ✓ C:\\Users\\$PC_USER\\zwift-launcher-keys.ps1 || echo   ✗ Missing: zwift-launcher-keys.ps1"

echo ""
echo "Scheduled Tasks:"
ssh "$PC_USER@$PC_IP" "schtasks /Query /TN LaunchZwiftRemote 2>nul >nul && echo   ✓ LaunchZwiftRemote || echo   ✗ Missing: LaunchZwiftRemote"
ssh "$PC_USER@$PC_IP" "schtasks /Query /TN LaunchSauceRemote 2>nul >nul && echo   ✓ LaunchSauceRemote || echo   ✗ Missing: LaunchSauceRemote"
ssh "$PC_USER@$PC_IP" "schtasks /Query /TN ZwiftLauncherKeys 2>nul >nul && echo   ✓ ZwiftLauncherKeys || echo   ✗ Missing: ZwiftLauncherKeys"

echo ""
echo "=========================================="
echo "  ✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "What was deployed:"
echo "  • LaunchZwiftRemote task - Launches Zwift Launcher"
echo "  • ZwiftLauncherKeys task - Automates launcher keyboard input"
echo "  • LaunchSauceRemote task - Launches Sauce for Zwift"
echo ""
echo "The API can now:"
echo "  1. Wake the PC via Wake-on-LAN"
echo "  2. Launch Zwift automatically"
echo "  3. Activate the launcher window (Tab, Tab, Enter)"
echo "  4. Launch Sauce for Zwift"
echo "  5. Set process priorities"
echo ""
echo "Test the automation:"
echo "  curl -X POST http://localhost:8000/api/v1/control/start"
echo ""
echo "Manual testing commands:"
echo "  # Test Zwift launch"
echo "  ssh $PC_USER@$PC_IP \"schtasks /Run /TN LaunchZwiftRemote\""
echo ""
echo "  # Test launcher activation (after Zwift launcher is running)"
echo "  ssh $PC_USER@$PC_IP \"schtasks /Run /TN ZwiftLauncherKeys\""
echo ""
echo "  # Test Sauce launch"
echo "  ssh $PC_USER@$PC_IP \"schtasks /Run /TN LaunchSauceRemote\""
echo ""
