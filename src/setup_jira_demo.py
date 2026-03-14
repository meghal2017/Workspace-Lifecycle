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

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import jira_client
from env_loader import load_env
import httpx
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Scenario Registry
# ---------------------------------------------------------------------------

SCENARIOS = {
    "profile": {
        "summary": "Feature: User Profile Management",
        "description": "As a user, I want to manage my personal information, notification preferences, and billing details in one place.",
        "acceptance_criteria": [
            "User can view their avatar, name, and email.",
            "User can update notification toggles (Email/SMS).",
            "Billing history displays a list of recent transactions.",
            "Mobile-responsive design across all breakpoints."
        ],
        "labels": ["frontend", "profile", "v1.0"],
        "children": [
            {
                "summary": "UI: Build Profile React Component",
                "desc": "Develop the React frontend with state management for profile forms."
            },
            {
                "summary": "Backend: Add GET/PUT /api/user/profile Endpoints",
                "desc": "Implement Node.js/Python endpoints with database integration."
            },
            {
                "summary": "Testing: E2E Cypress Tests for Profile",
                "desc": "Automated regression suite for name updates and validation errors."
            }
        ]
    },
    "auth": {
        "summary": "Security: Multi-Factor Authentication (MFA)",
        "description": "Improve platform security by implementing Time-based One-Time Password (TOTP) for all administrative accounts.",
        "acceptance_criteria": [
            "Enable TOTP secret generation via QR code.",
            "Enforce MFA challenge on login for 'Admin' role.",
            "Provide backup recovery codes for users.",
            "Audit logs must record all MFA enablement events."
        ],
        "labels": ["security", "auth", "critical"],
        "children": [
            {
                "summary": "Logic: TOTP Secret Generation & QR API",
                "desc": "Implement the core vault logic for secret storage and QR code generation."
            },
            {
                "summary": "UI: MFA Setup & Verification Screens",
                "desc": "Design the setup flow and the challenge prompt UI."
            },
            {
                "summary": "Audit: Integration with Security Logs",
                "desc": "Ensure all MFA attempts are logged for compliance monitoring."
            }
        ]
    },
    "search": {
        "summary": "Platform: Semantic Product Search",
        "description": "Replace existing keyword search with a vector-based semantic search to improve discovery relevance.",
        "acceptance_criteria": [
            "Support natural language queries (e.g., 'warm winter gear').",
            "Latency must remain under 200ms for 95th percentile.",
            "Integrate with Pinecone/Milvus vector database.",
            "Highlight relevant keywords in search results."
        ],
        "labels": ["platform", "search", "ai"],
        "children": [
            {
                "summary": "Infra: Provision Vector DB & Indexing",
                "desc": "Set up the vector database and pipeline for product indexing."
            },
            {
                "summary": "Model: Deploy Embedding Inference Service",
                "desc": "Host the NLP model to convert queries into vectors."
            },
            {
                "summary": "UI: New Search Results Layout",
                "desc": "Build a modern masonry-style grid for displayed products."
            }
        ]
    }
}

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", help="Specific scenario key (profile, auth, search)")
    args = parser.parse_args()

    load_env(override=True)
    if not jira_client.jira_enabled():
        print("❌ Error: Jira credentials not set.")
        sys.exit(1)

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
    print(f"Next step: ./bin/cli.sh load-epic {parent_key}")

if __name__ == "__main__":
    asyncio.run(main())

