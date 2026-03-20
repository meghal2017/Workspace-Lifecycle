#!/usr/bin/env bash
# run: source setup_demo.sh

# Get the absolute path to the directory containing this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Define functions for the commands
function setup-demo() {
    "$DIR/bin/cli.sh" setup-demo "$@"
}

function teardown-demo() {
    "$DIR/bin/cli.sh" teardown-demo "$@"
}

function cleanup-workspace() {
    "$DIR/bin/cli.sh" cleanup-workspace "$@"
}

function load-epic() {
    "$DIR/bin/cli.sh" load-epic "$@"
}

function approve-plan() {
    "$DIR/bin/cli.sh" approve-plan "$@"
}

function approve-subtask() {
    "$DIR/bin/cli.sh" approve-subtask "$@"
}

function close-epic() {
    "$DIR/bin/cli.sh" close-epic "$@"
}

function query-wf() {
    "$DIR/bin/cli.sh" query-wf "$@"
}

function query() {
    "$DIR/bin/cli.sh" query "$@"
}

echo "✅ Working shortcuts loaded into your current shell session!"
echo ""
echo "Multi-Agent Loop POC Flow:"
echo "  setup-demo [--scenario <name>]           - Create a real dummy Epic and 3 Story child-tasks in Jira"
echo "                                             Scenarios: profile, auth, search"
echo "  load-epic <Epic Name>                    - Start workflow and generate Initial Spec"
echo "  query-wf <Key>           (Tracks individual agents in real-time)"
echo "  approve-plan <Key>       (Unblocks agent tasks)"
echo "  approve-subtask <Key> <Child Key> (Individually approves subtasks)"
echo "  close-epic <Key>         (Final cleanup)"
