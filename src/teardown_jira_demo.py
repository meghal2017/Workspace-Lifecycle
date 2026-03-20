#!/usr/bin/env python3
"""
teardown_jira_demo.py — Deletes a specific Jira Epic and all its linked child issues.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import jira_client
from env_loader import load_env


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Teardown an Epic and its children.")
    parser.add_argument("epic_key", nargs="?", help="Epic key to teardown (e.g. WL-1 or PROFILE)")
    parser.add_argument("--offline", action="store_true", help="Teardown from the simulation directory.")
    args = parser.parse_args()

    load_env(override=True)
    if args.offline:
        os.environ["JIRA_OFFLINE"] = "true"
    elif not jira_client.jira_enabled():
        print("❌ Error: Jira credentials not set. Use --offline to teardown simulated data.")
        sys.exit(1)

    if not args.epic_key:
        parser.print_help()
        sys.exit(1)

    epic_key = args.epic_key
    print(f"🗑️  Tearing down Epic '{epic_key}' (Offline: {args.offline})...\n")

    # Fetch child issues
    try:
        children = await jira_client.get_child_issues(epic_key)
        for child in children:
            child_key = child["key"]
            print(f"   Deleting child issue: {child_key}...")
            await jira_client.delete_issue(child_key)
            print(f"   ✅ Deleted {child_key}")
    except Exception as e:
        print(f"   ⚠️ Could not fetch or delete child issues: {e}")

    # Delete parent epic
    try:
        print(f"   Deleting parent issue: {epic_key}...")
        await jira_client.delete_issue(epic_key)
        print(f"   ✅ Deleted Parent {epic_key}")
    except Exception as e:
        print(f"   ❌ Failed to delete parent issue {epic_key}. Error: {e}")
        sys.exit(1)

    print("\n🎉 Teardown complete!")

if __name__ == "__main__":
    asyncio.run(main())
