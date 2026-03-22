#!/usr/bin/env bash
# run_demo.sh - A shortcut script to run the Workspace Lifecycle workflow

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
STARTER="python3 $DIR/src/starter.py"
SETUP_JIRA="python3 $DIR/src/setup_jira_demo.py"
TEARDOWN_JIRA="python3 $DIR/src/teardown_jira_demo.py"

SCENARIO="profile"
OFFLINE=""

# Simple argument parsing
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --scenario) SCENARIO="$2"; shift ;;
        --offline) OFFLINE="--offline" ;;
        *) SCENARIO="$1" ;; # Positional argument as scenario
    esac
    shift
done

echo "=========================================================="
echo "Workspace Lifecycle Worker — Multi-Agent Loop Demo"
echo "  Mode: ${OFFLINE:-online}"
echo "=========================================================="

echo -e "\n1. Initializing Demo Scenario: $SCENARIO..."
# Run setup and capture output to find the new Epic Key
SETUP_OUTPUT=$($SETUP_JIRA --scenario "$SCENARIO" $OFFLINE)
echo "$SETUP_OUTPUT"

EPIC_ID=$(echo "$SETUP_OUTPUT" | grep "Next step: load-epic" | awk '{print $NF}')

if [ -z "$EPIC_ID" ]; then
    echo "❌ Error: Could not extract Epic Key from setup output."
    exit 1
fi

echo -e "\n   Press Enter to LOAD IT into the workflow: $EPIC_ID..."
read

EPIC_ID_LOWER=$(echo "$EPIC_ID" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
WORKFLOW_ID="workspace-lc-$EPIC_ID_LOWER"

echo -e "\n2. Loading $EPIC_ID..."
$STARTER --load-epic "$EPIC_ID"

echo -e "\n   Review v1: simulated_jira/$EPIC_ID/spec_epic.md"
echo "   Press Enter to APPROVE the plan..."
read

echo -e "\n3. Approving Plan..."
$STARTER --approve-plan "$WORKFLOW_ID"

echo -e "\n   🚀 Plan Approved! Waiting 5s for agents to start work..."
sleep 5

echo "   Press Enter to query the DASHBOARD..."
read
$STARTER --status "$WORKFLOW_ID"

echo -e "\n4. Approving Subtasks..."
SUBTASKS=$($STARTER --list-subtasks "$WORKFLOW_ID")

if [ -z "$SUBTASKS" ]; then
    echo "⚠️ Waiting for subtasks..."
    sleep 2
    SUBTASKS=$($STARTER --list-subtasks "$WORKFLOW_ID")
fi

echo "   Press Enter to approve ALL subtasks: $SUBTASKS"
read

for SID in $SUBTASKS; do
    echo "   Approving $SID..."
    $STARTER --approve-subtask "$WORKFLOW_ID" "$SID"
done

echo -e "\n   Final Results Ready. Checking status..."
$STARTER --status "$WORKFLOW_ID"

echo -e "\n   Ready to close the workspace."
echo "   Press Enter to send the FINAL sign-off..."
read

echo -e "\n5. Closing Epic..."
$STARTER --close-epic "$WORKFLOW_ID" --comment "Demo complete."

echo -e "\n   Review v3: simulated_jira/$EPIC_ID/spec_epic.md"
echo "   Press Enter to continue to teardown step..."
read

echo -en "\n❓ Tear down the demo data $EPIC_ID? (y/n): "
read -r CONFIRM
if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo -e "\n6. Tearing down demo data..."
    $TEARDOWN_JIRA "$EPIC_ID" $OFFLINE
else
    echo -e "\nSkipping teardown."
fi

echo -e "\n✅ Demo complete!"
