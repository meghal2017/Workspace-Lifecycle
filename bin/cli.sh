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
    echo "  query-wf <Epic Name>                     - Query detailed subtask/epic status"
    echo "  approve-plan <Epic Name>                 - Approve the implementation plan to begin agent tasks"
    echo "  reset-wf <Epic Name>                     - Terminate a stuck workflow"

    echo "  approve-subtask <Epic Name> <Subtask ID> - Approve a specific agent resolution"
    echo "  close-epic <Epic Name> -comment <Text>   - Final human approval and archive workspace"
    echo "  sample-commands <Epic Name>              - Show sample commands for a specific epic"
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
    SCENARIO="profile"
    OFFLINE=""
    
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --scenario) SCENARIO="$2"; shift ;;
            --offline) OFFLINE="--offline" ;;
        esac
        shift
    done
    
    python3 "$DIR/src/setup_jira_demo.py" --scenario "$SCENARIO" $OFFLINE
    exit 0
fi

if [ "$COMMAND" == "cleanup-workspace" ]; then
    OFFLINE=""
    if [ "$2" == "--offline" ]; then OFFLINE="--offline"; fi
    python3 "$DIR/src/cleanup_jira_workspace.py" $OFFLINE
    exit 0
fi

EPIC_NAME=$2

if [ "$COMMAND" == "teardown-demo" ]; then
    EPIC_NAME=$2
    OFFLINE=""
    if [ "$3" == "--offline" ]; then OFFLINE="--offline"; fi
    
    if [ -z "$EPIC_NAME" ]; then
        echo "Error: You must provide an Epic Name (e.g. WL-1) to teardown."
        exit 1
    fi
    python3 "$DIR/src/teardown_jira_demo.py" "$EPIC_NAME" $OFFLINE
    exit 0
fi

# # if [ -z "$EPIC_NAME" ]; then
# #     echo "Error: <Epic Name> is required."
# #     echo ""
# #     show_help
# #     exit 1
# # fi

EPIC_NAME_LOWER=$(echo "$EPIC_NAME" | tr '[:upper:]' '[:lower:]')
WORKFLOW_ID="workspace-lc-$EPIC_NAME_LOWER"

# Parse optional -comment flag
COMMENT=""
if [ "$3" == "-comment" ] && [ -n "$4" ]; then
    COMMENT="$4"
fi

case $COMMAND in
    load-epic)
        if [ -z "$EPIC_NAME" ]; then echo "Error: <Epic Name> is required."; exit 1; fi
        $STARTER --load-epic "$EPIC_NAME_LOWER"
        ;;
    query)
        if [ -z "$EPIC_NAME" ]; then echo "Error: <Epic Name> is required."; exit 1; fi
        $STARTER --query "$WORKFLOW_ID"
        ;;
    query-wf)
        if [ -z "$EPIC_NAME" ]; then echo "Error: <Epic Name> is required."; exit 1; fi
        $STARTER --status "$WORKFLOW_ID"
        ;;
    reset-wf)
        if [ -z "$EPIC_NAME" ]; then echo "Error: <Epic Name> is required."; exit 1; fi
        $STARTER --terminate "$WORKFLOW_ID"
        ;;
    approve-plan)
        if [ -z "$EPIC_NAME" ]; then echo "Error: <Epic Name> is required."; exit 1; fi
        $STARTER --approve-plan "$WORKFLOW_ID"
        ;;
    approve-subtask)
        if [ -z "$EPIC_NAME" ]; then echo "Error: <Epic Name> is required."; exit 1; fi
        SUBTASK_ID=$3
        if [ -z "$SUBTASK_ID" ]; then
            echo "Error: <Subtask ID> is required for approve-subtask."
            exit 1
        fi
        $STARTER --approve-subtask "$WORKFLOW_ID" "$SUBTASK_ID"
        ;;
    close-epic)
        if [ -z "$EPIC_NAME" ]; then echo "Error: <Epic Name> is required."; exit 1; fi
        if [ -z "$COMMENT" ]; then
            $STARTER --close-epic "$WORKFLOW_ID"
        else
            $STARTER --close-epic "$WORKFLOW_ID" --comment "$COMMENT"
        fi
        ;;
    sample-commands)
        if [ -z "$EPIC_NAME" ]; then
            EPIC_NAME="WL-1"
        fi
        echo "# Sample commands for $EPIC_NAME:"
        echo "setup-demo --scenario profile"
        echo "load-epic $EPIC_NAME"
        echo "approve-plan $EPIC_NAME"
        echo "query-wf $EPIC_NAME"
        echo "approve-subtask $EPIC_NAME <SUBTASK_ID>"
        echo "close-epic $EPIC_NAME -comment \"Ship it!\""
        echo "teardown-demo $EPIC_NAME"
        echo "cleanup-workspace"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
