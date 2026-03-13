#!/usr/bin/env bash
# run_demo.sh - A shortcut script to run the Workspace Lifecycle workflow

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
STARTER="python3 $DIR/src/starter.py"

echo "=========================================================="
echo "Workspace Lifecycle Worker — Demo Shortcut"
echo "=========================================================="

echo -e "\n1. Loading Epic (EPIC-001)..."
$STARTER --load-epic EPIC-001

echo -e "\n⏳ Press Enter to trigger the analysis agents (start-work)..."
read

echo -e "\n2. Starting Work (Agent Scans)..."
$STARTER --start-work workspace-lc-EPIC-001

echo -e "\n⏳ Press Enter to approve the agent results (approve-work)..."
read

echo -e "\n3. Approving Work..."
$STARTER --approve-work workspace-lc-EPIC-001 --comment "Looks correct"

echo -e "\n⏳ Press Enter to finalize the workspace (close-epic)..."
read

echo -e "\n4. Closing Epic (Final Approval)..."
$STARTER --close-epic workspace-lc-EPIC-001 --comment "Ship it"

echo -e "\nDone! Check the specs/Spec.md file for the final output."
