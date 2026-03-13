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

function start-work() {
    "$DIR/bin/cli.sh" start-work "$@"
}

function approve-work() {
    "$DIR/bin/cli.sh" approve-work "$@"
}

function close-epic() {
    "$DIR/bin/cli.sh" close-epic "$@"
}

echo "✅ Working shortcuts loaded into your current shell session!"
echo ""
echo "Try running:"
echo "  setup-demo"
echo "  teardown-demo WL-1"
echo "  cleanup-workspace"
echo "  load-epic WL-10"
