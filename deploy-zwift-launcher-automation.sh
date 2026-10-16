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

# Step 1: Locate the PowerShell script (single source of truth in this repo)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_SCRIPT="$SCRIPT_DIR/windows/zwift-launcher-keys.ps1"
[ -f "$KEYS_SCRIPT" ] || { echo "Missing $KEYS_SCRIPT" >&2; exit 1; }

# Step 2: Copy script to Windows PC
echo "Copying PowerShell script to PC..."
scp "$KEYS_SCRIPT" "$PC_USER@$PC_IP:C:/Users/$PC_USER/zwift-launcher-keys.ps1"

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
