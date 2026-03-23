#!/usr/bin/env python3
"""
cleanup_jira_workspace.py — DANGEROUS: Deletes ALL issues in the configured Jira Project.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import jira_client
from env_loader import load_env


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cleanup the Jira project (or simulation).")
    parser.add_argument("--offline", action="store_true", help="Cleanup the offline simulation instead of real Jira.")
    args = parser.parse_known_args()[0]

    load_env(override=True)
    if args.offline:
        os.environ["JIRA_OFFLINE"] = "true"
        print("🛠️  Offline Mode: Preparing to wipe the simulated Jira directory...")
        project_key = "SIM"
    elif not jira_client.jira_enabled():
        print("❌ Error: Jira credentials not set. Use --offline to cleanup simulated data.")
        sys.exit(1)
    else:
        project_key = os.environ.get("JIRA_PROJECT_KEY")
        if not project_key:
            print("❌ Error: JIRA_PROJECT_KEY not found.")
            sys.exit(1)
        print(f"⚠️  WARNING: You are about to wipe out ALL tickets in Jira project '{project_key}'.")
    
    confirm = input("Are you absolutely sure? [y/N]: ")
    if confirm.lower() not in ("yes", "y"):
        print("Aborting cleanup.")
        sys.exit(0)

    target = "Simulated Jira Board" if args.offline else f"Jira Project '{project_key}'"
    print(f"\n🗑️  Wiping {target}...\n")

    try:
        if args.offline:
            # Deep clean for offline mode: Wipe the entire simulation directory
            import shutil
            import jira_simulator
            sim_dir = jira_simulator.SIM_DIR
            if os.path.exists(sim_dir):
                print(f"   Wiping simulation directory: {sim_dir}...")
                shutil.rmtree(sim_dir)
                os.makedirs(sim_dir, exist_ok=True)
            print("\n🎉 Online simulation cleanup complete! All artifacts and directories have been purged.")
            sys.exit(0)

        # Online Search all issues in the project
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
