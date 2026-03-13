#!/usr/bin/env bash
# bin/cli.sh - Command line wrapper for the Workspace Lifecycle Worker

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
STARTER="python3 $DIR/src/starter.py"

function show_help {
    echo "Usage:"
    echo "  setup-demo                               - Create a real dummy Epic in your Jira project"
    echo "  teardown-demo <Epic Name>                - Delete a specific test Epic and its child tasks"
    echo "  cleanup-workspace                        - DANGEROUS: Wipe ALL issues from the Jira project"
    echo "  load-epic <Epic Name>                    - Start workflow and generate Spec v1"
    echo "  start-work <Epic Name>                   - Trigger analysis agents"
    echo "  approve-work <Epic Name> -comment <Text> - Approve agent results"
    echo "  close-epic <Epic Name> -comment <Text>   - Final human approval and close"
    echo ""
    echo "Example:"
    echo "  ./bin/cli.sh setup-demo"
    echo "  ./bin/cli.sh teardown-demo WL-1"
    echo "  ./bin/cli.sh load-epic WL-10"
}

if [ -z "$1" ]; then
    show_help
    exit 1
fi

COMMAND=$1

if [ "$COMMAND" == "setup-demo" ]; then
    python3 "$DIR/src/setup_jira_demo.py"
    exit 0
fi

if [ "$COMMAND" == "cleanup-workspace" ]; then
    python3 "$DIR/src/cleanup_jira_workspace.py"
    exit 0
fi

EPIC_NAME=$2

if [ "$COMMAND" == "teardown-demo" ]; then
    if [ -z "$EPIC_NAME" ]; then
        echo "Error: You must provide an Epic Name (e.g. WL-1) to teardown."
        exit 1
    fi
    python3 "$DIR/src/teardown_jira_demo.py" "$EPIC_NAME"
    exit 0
fi

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
