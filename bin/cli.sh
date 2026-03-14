#!/usr/bin/env bash
# bin/cli.sh - Command line wrapper for the Workspace Lifecycle Worker

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
STARTER="python3 $DIR/src/starter.py"

function show_help {
    echo "Usage:"
    echo "  setup-demo                               - Create a real dummy Epic and 3 Story child-tasks in Jira"
    echo "  load-epic <Epic Name>                    - Start workflow and generate Initial Spec"
    echo "  query <Epic Name>                        - Query the current phase of the workflow"
    echo "  approve-plan <Epic Name>                 - Approve the implementation plan to begin agent tasks"

    echo "  approve-subtask <Epic Name> <Subtask ID> - Approve a specific agent resolution"
    echo "  close-epic <Epic Name> -comment <Text>   - Final human approval and archive workspace"
    echo "  teardown-demo <Epic Name>                - Delete a specific test Epic and its child tasks"
    echo "  cleanup-workspace                        - DANGEROUS: Wipe ALL issues from the Jira project"
    echo ""
}

if [ -z "$1" ]; then
    show_help
    exit 1
fi

COMMAND=$1

if [ "$COMMAND" == "setup-demo" ]; then
    if [ "$2" == "--scenario" ] && [ -n "$3" ]; then
        python3 "$DIR/src/setup_jira_demo.py" --scenario "$3"
    else
        python3 "$DIR/src/setup_jira_demo.py"
    fi
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
    query)
        $STARTER --query "$WORKFLOW_ID"
        ;;
    approve-plan)

        $STARTER --approve-plan "$WORKFLOW_ID"
        ;;
    approve-subtask)
        SUBTASK_ID=$3
        if [ -z "$SUBTASK_ID" ]; then
            echo "Error: <Subtask ID> is required for approve-subtask."
            exit 1
        fi
        $STARTER --approve-subtask "$WORKFLOW_ID" "$SUBTASK_ID"
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
