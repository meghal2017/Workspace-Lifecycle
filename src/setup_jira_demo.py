#!/usr/bin/env python3
"""
setup_jira_demo.py — Programmatically creates a demo Jira Epic and child tasks.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import jira_client
from env_loader import load_env
import httpx
from datetime import datetime, timezone, timedelta

async def add_to_active_sprint(project_key: str, issue_keys: list):
    """Attempt to find the project board and move issues into an active sprint."""
    base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    email = os.environ.get("JIRA_USER_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    auth = (email, token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    print("\n3️⃣  Moving issues to the Active Board (Sprint)...")
    async with httpx.AsyncClient(auth=auth) as c:
        # 1. Find the board
        r = await c.get(f"{base_url}/rest/agile/1.0/board?projectKeyOrId={project_key}", headers=headers)
        if r.status_code != 200:
            print("   ⚠️ Could not fetch Jira Agile boards. Issues may reside in backlog.")
            return
            
        boards = r.json().get("values", [])
        if not boards:
            print("   ⚠️ No boards found for this project.")
            return
        
        board_id = boards[0]["id"]
        
        # 2. Find sprints for the board
        r = await c.get(f"{base_url}/rest/agile/1.0/board/{board_id}/sprint", headers=headers)
        sprints = r.json().get("values", [])
        if not sprints:
            print("   ⚠️ No Sprints found on this board. Active Board may be disabled.")
            return

        # 3. Prefer an active sprint, else take the first future sprint
        active_sprint = next((s for s in sprints if s["state"] == "active"), None)
        sprint_to_use = active_sprint or sprints[0]
        sprint_id = sprint_to_use["id"]
        
        # 4. Move issues
        r = await c.post(
            f"{base_url}/rest/agile/1.0/sprint/{sprint_id}/issue", 
            headers=headers, 
            json={"issues": issue_keys}
        )
        if r.status_code < 400:
            print(f"   ✅ Moved issues to Sprint '{sprint_to_use['name']}'")
        
        # 5. If sprint is not active, attempt to start it
        if sprint_to_use["state"] != "active":
            now = datetime.now(timezone.utc)
            end = now + timedelta(days=14)
            payload = {
                "state": "active",
                "startDate": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "endDate": end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
            r = await c.post(f"{base_url}/rest/agile/1.0/sprint/{sprint_id}", headers=headers, json=payload)
            if r.status_code == 200:
                print(f"   ✅ Activated Sprint '{sprint_to_use['name']}'")
            else:
                print(f"   ⚠️ Sprint assigned, but could not autostart it. You may need to click 'Start Sprint' in Jira.")


async def main():
    load_env(override=True)
    if not jira_client.jira_enabled():
        print("❌ Error: Jira credentials not set in environment.")
        print("Please check your .env file and ensure JIRA_BASE_URL, JIRA_USER_EMAIL, and JIRA_API_TOKEN are set.")
        sys.exit(1)

    project_key = os.environ.get("JIRA_PROJECT_KEY")
    if not project_key:
        print("❌ Error: JIRA_PROJECT_KEY not found in environment.")
        sys.exit(1)

    print(f"🚀 Connecting to Jira to set up a demo Epic in project '{project_key}'...\n")

    # 1. Create the parent Epic
    # We use type 'Task' or 'Story' as a fallback if 'Epic' gives custom-field errors,
    # but let's attempt 'Epic' first. If it's a Company-managed project it might fail
    # without 'Epic Name', but Team-managed projects allow it.
    # To be universally safe for the demo, we'll create a "Story" and link sub-tasks
    # or just normal tasks to it. The workflow just needs an issue key.
    
    parent_fields = {
        "project": {"key": project_key},
        "summary": "Implement Unified Authentication Gateway",
        "description": jira_client._adf_text(
            "As a platform engineer, I need a unified authentication gateway to standardize "
            "login across all microservices.\n\n"
            "Acceptance Criteria:\n"
            "- Must support OAuth2 and SAML.\n"
            "- Latency under 50ms.\n"
            "- High availability (99.99%)."
        ),
        "issuetype": {"name": "Story"},
    }

    try:
        print("1️⃣  Creating Parent Issue (Story)...")
        parent_resp = await jira_client.create_issue(parent_fields)
        parent_key = parent_resp["key"]
        print(f"   ✅ Created Parent: {parent_key}")
    except Exception as e:
        print(f"   ❌ Failed to create parent issue. Is the JIRA_PROJECT_KEY correct? Error: {e}")
        sys.exit(1)

    # 2. Create child issues
    child_summaries = [
        "Create database schemas for Auth profiles",
        "Implement OAuth2 token exchange endpoints",
        "Write integration tests for SAML provider"
    ]

    child_keys = []
    print("\n2️⃣  Creating Child Issues...")
    for idx, summary in enumerate(child_summaries, 1):
        child_fields = {
            "project": {"key": project_key},
            "summary": summary,
            "description": jira_client._adf_text(f"Detailed implementation for: {summary}"),
            "issuetype": {"name": "Task"},
            # Modern Jira allows setting parent directly on creation for sub-tasks or linked hierarchy
            "parent": {"key": parent_key}
        }
        try:
            # We will try to create with parent set. If it fails (e.g. issues types don't allow parent),
            # we will create without parent and link them.
            child_resp = await jira_client.create_issue(child_fields)
            child_keys.append(child_resp['key'])
            print(f"   ✅ Created Child {idx}: {child_resp['key']}")
        except Exception:
            # Fallback to creating independently and linking
            del child_fields["parent"]
            child_resp = await jira_client.create_issue(child_fields)
            child_key = child_resp['key']
            child_keys.append(child_key)
            print(f"   ✅ Created Child {idx}: {child_key} (Linking...)")
            await jira_client.link_issue(inward_key=parent_key, outward_key=child_key, link_type_name="Relates")

    # Move all newly created issues to an Active Sprint
    await add_to_active_sprint(project_key, [parent_key] + child_keys)

    print(f"\n🎉 Demo setup complete! Your environment is ready.")
    print("-" * 50)
    print(f"Next step: Run the full workflow on this issue:")
    print(f"  load-epic {parent_key}")
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
