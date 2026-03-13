#!/usr/bin/env bash
# bin/cli.sh - Command line wrapper for the Workspace Lifecycle Worker

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
STARTER="python3 $DIR/src/starter.py"

function show_help {
    echo "Usage:"
    echo "  load-epic <Epic Name>                    - Start workflow and generate Spec v1"
    echo "  start-work <Epic Name>                   - Trigger analysis agents"
    echo "  approve-work <Epic Name> -comment <Text> - Approve agent results"
    echo "  close-epic <Epic Name> -comment <Text>   - Final human approval and close"
    echo ""
    echo "Example:"
    echo "  ./bin/cli.sh load-epic EPIC-001"
}

if [ -z "$1" ]; then
    show_help
    exit 1
fi

COMMAND=$1
EPIC_NAME=$2

if [ -z "$EPIC_NAME" ]; then
    echo "Error: <Epic Name> is required."
    echo ""
    show_help
    exit 1
fi

WORKFLOW_ID="workspace-lc-$EPIC_NAME"

# Parse optional -comment flag
COMMENT=""
if [ "$3" == "-comment" ] && [ -n "$4" ]; then
    COMMENT="$4"
fi

case $COMMAND in
    load-epic)
        $STARTER --load-epic "$EPIC_NAME"
        ;;
    start-work)
        $STARTER --start-work "$WORKFLOW_ID"
        ;;
    approve-work)
        if [ -z "$COMMENT" ]; then
            $STARTER --approve-work "$WORKFLOW_ID"
        else
            $STARTER --approve-work "$WORKFLOW_ID" --comment "$COMMENT"
        fi
        ;;
    close-epic)
        if [ -z "$COMMENT" ]; then
            $STARTER --close-epic "$WORKFLOW_ID"
        else
            $STARTER --close-epic "$WORKFLOW_ID" --comment "$COMMENT"
        fi
        ;;
    *)
        echo "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
