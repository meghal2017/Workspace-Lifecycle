#!/usr/bin/env python3
"""
setup_jira_demo.py — Programmatically creates a demo Jira Epic and child tasks.
Supports multiple rich scenarios.
"""
import asyncio
import os
import sys
import random
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("setup-jira-demo")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import jira_client
from env_loader import load_env
import httpx
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Scenario Registry
# ---------------------------------------------------------------------------

from scenarios import SCENARIOS

async def add_to_active_sprint(project_key: str, issue_keys: list):
    """Attempt to find the project board and move issues into an active sprint."""
    base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    email = os.environ.get("JIRA_USER_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    auth = (email, token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    print("\n3️⃣  Moving issues to the Active Board (Sprint)...")
    async with httpx.AsyncClient(auth=auth) as c:
        try:
            r = await c.get(f"{base_url}/rest/agile/1.0/board?projectKeyOrId={project_key}", headers=headers)
            if r.status_code != 200:
                print("   ⚠️ Could not fetch Jira Agile boards.")
                return
                
            boards = r.json().get("values", [])
            if not boards: return
            
            board_id = boards[0]["id"]
            r = await c.get(f"{base_url}/rest/agile/1.0/board/{board_id}/sprint", headers=headers)
            sprints = r.json().get("values", [])
            if not sprints: return

            active_sprint = next((s for s in sprints if s["state"] == "active"), None)
            sprint_to_use = active_sprint or sprints[0]
            sprint_id = sprint_to_use["id"]
            
            await c.post(f"{base_url}/rest/agile/1.0/sprint/{sprint_id}/issue", headers=headers, json={"issues": issue_keys})
            print(f"   ✅ Moved to Sprint '{sprint_to_use['name']}'")
        except Exception as e:
            print(f"   ⚠️ Agile/Sprint move failed: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Bootstrap a Jira Epic for the demo workflow.")
    parser.add_argument("--scenario", default="profile", choices=SCENARIOS.keys(), help="Which scenario to use.")
    parser.add_argument("--offline", action="store_true", help="Force run in Offline Mode (ignore Jira credentials)")
    args = parser.parse_known_args()[0]

    load_env(override=True)

    if args.offline or not jira_client.jira_enabled():
        logger.info(f"Offline Mode: Initializing simulation for scenario '{args.scenario}'...")
        import jira_simulator
        
        # Generate a "Real-looking" Key (e.g. SIM-1 or project-key-1)
        project_key = os.environ.get("JIRA_PROJECT_KEY", "SIM")
        # Ensure we have a unique-ish number for the session
        num = len(jira_simulator.search_issues('')) + 1
        sim_key = f"{project_key}-{num}"
        
        jira_simulator.initialize_scenario(args.scenario, SCENARIOS[args.scenario], key=sim_key)
        
        print(f"\n✅ Simulation initialized as {sim_key}")
        print(f"Next step: load-epic {sim_key}\n")
        return

    # Online mode logic continues...
    project_key = os.environ.get("JIRA_PROJECT_KEY")
    if not project_key:
        print("❌ Error: JIRA_PROJECT_KEY not found.")
        sys.exit(1)

    # 1. Select Scenario
    s_key = args.scenario if args.scenario in SCENARIOS else random.choice(list(SCENARIOS.keys()))
    scenario = SCENARIOS[s_key]
    print(f"🚀 Setting up scenario: [{s_key.upper()}] - {scenario['summary']}\n")

    # 2. Format Description with Acceptance Criteria
    desc_body = scenario['description'] + "\n\n**Acceptance Criteria:**\n"
    for ac in scenario['acceptance_criteria']:
        desc_body += f"- {ac}\n"

    # 3. Create Parent Epic
    parent_fields = {
        "project": {"key": project_key},
        "summary": scenario["summary"],
        "description": jira_client._adf_text(desc_body),
        "issuetype": {"name": "Epic"},
        "labels": scenario["labels"]
    }

    try:
        print("1️⃣  Creating Parent Epic...")
        parent_resp = await jira_client.create_issue(parent_fields)
        parent_key = parent_resp["key"]
        print(f"   ✅ Created: {parent_key}")
    except Exception as e:
        print(f"   ❌ Failed to create Epic: {e}")
        sys.exit(1)

    # 4. Create Child Stories
    child_keys = []
    print("\n2️⃣  Creating Subtasks...")
    for story in scenario["children"]:
        desc = story["desc"]
        if story.get("plan_steps"):
            desc += "\n\n**Implementation Plan:**\n"
            for step in story["plan_steps"]:
                desc += f"- {step}\n"

        child_fields = {
            "project": {"key": project_key},
            "summary": story["summary"],
            "description": jira_client._adf_text(desc),
            "issuetype": {"name": "Story"},
            "labels": scenario["labels"]
        }
        try:
            child_resp = await jira_client.create_issue(child_fields)
            ckey = child_resp['key']
            child_keys.append(ckey)
            await jira_client.link_issue(ckey, parent_key, "Relates")
            print(f"   ✅ Created Child: {ckey}")
        except Exception as e:
            print(f"   ⚠️ Failed to create/link child: {e}")

    # 5. Agile Cleanup
    await add_to_active_sprint(project_key, [parent_key] + child_keys)

    print(f"\n🎉 Demo setup complete! Scenario: {s_key}")
    print(f"Next step: load-epic {parent_key}")

if __name__ == "__main__":
    asyncio.run(main())

