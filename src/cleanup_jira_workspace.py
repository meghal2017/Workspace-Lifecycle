#!/usr/bin/env python3
"""
cleanup_jira_workspace.py — DANGEROUS: Deletes ALL issues in the configured Jira Project.
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

    project_key = os.environ.get("JIRA_PROJECT_KEY")
    if not project_key:
        print("❌ Error: JIRA_PROJECT_KEY not found in environment.")
        sys.exit(1)

    print("⚠️  WARNING: You are about to wipe out ALL tickets in the Jira project workspace.")
    print(f"Project Key: {project_key}")
    
    confirm = input("Are you absolutely sure? Type 'YES' to permanently format the board: ")
    if confirm != "YES":
        print("Aborting cleanup.")
        sys.exit(0)

    print(f"\n🗑️  Wiping Jira Project '{project_key}'...\n")

    try:
        # Search all issues in the project
        jql = f'project = "{project_key}"'
        issues = await jira_client.search_issues(jql)
        
        if not issues:
            print("   ✅ Project is already empty. Nothing to clean up.")
            sys.exit(0)

        deleted_count = 0
        for issue in issues:
            issue_key = issue["key"]
            print(f"   Deleting issue: {issue_key}...")
            try:
                await jira_client.delete_issue(issue_key)
                print(f"   ✅ Deleted {issue_key}")
                deleted_count += 1
            except Exception as e:
                print(f"   ❌ Failed to delete {issue_key}: {e}")

        print(f"\n🎉 Workspace cleanup complete! Permanently deleted {deleted_count} issues.")

    except Exception as e:
        print(f"   ❌ Could not execute search or delete: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
