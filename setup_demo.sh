#!/usr/bin/env bash
# run: source setup_demo.sh

# Get the absolute path to the directory containing this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Define functions for the commands
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
echo "  load-epic EPIC-001"
