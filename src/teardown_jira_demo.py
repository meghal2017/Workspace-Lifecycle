#!/usr/bin/env python3
"""
teardown_jira_demo.py — Deletes a specific Jira Epic and all its linked child issues.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import jira_client
from dotenv import load_dotenv


async def main():
    load_dotenv(override=True)
    if not jira_client.jira_enabled():
        print("❌ Error: Jira credentials not set in environment.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python3 teardown_jira_demo.py <EPIC_KEY>")
        print("Example: python3 teardown_jira_demo.py WL-1")
        sys.exit(1)

    epic_key = sys.argv[1]
    print(f"🗑️  Tearing down test Epic '{epic_key}' and its children...\n")

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
