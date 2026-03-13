"""
activities.py — All Temporal @activity definitions for the Workspace Lifecycle Worker.

Each activity is a plain async function decorated with @activity.defn.
Activities are the units that get retried on failure; they are NOT replayed
like workflow code — they run against real I/O (files, APIs, etc.).
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from temporalio import activity

import jira_client

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SPECS_DIR = os.path.join(_PROJECT_ROOT, "specs")


def _spec_path() -> str:
    os.makedirs(_SPECS_DIR, exist_ok=True)
    return os.path.join(_SPECS_DIR, "Spec.md")


# ---------------------------------------------------------------------------
# Activity: Ingest Jira Epic
# ---------------------------------------------------------------------------

@activity.defn
async def ingest_jira_epic(epic_id: str) -> Dict[str, Any]:
    """
    Step 1 — Load the real Jira Epic and return it as a serialisable dict.
    """
    logger = activity.logger
    logger.info(f"[ingest_jira_epic] Fetching real Jira issue: {epic_id}")

    # 1. Fetch main issue
    issue_data = await jira_client.get_issue(epic_id)
    fields = issue_data.get("fields", {})
    
    # 2. Fetch child issues
    child_issues = await jira_client.get_child_issues(epic_id)
    child_stories = [f"{child['key']} - {child.get('fields', {}).get('summary', '')}" for child in child_issues]
    
    # 3. Parse ADF description
    description_text = jira_client.adf_to_text(fields.get("description"))
    
    priority_name = fields.get("priority", {}).get("name", "Medium") if fields.get("priority") else "Medium"
    status_name = fields.get("status", {}).get("name", "To Do") if fields.get("status") else "To Do"
    
    epic = {
        "id": issue_data.get("id", ""),
        "key": issue_data.get("key", epic_id),
        "summary": fields.get("summary", ""),
        "description": description_text,
        "assets": [],  # Could be pulled from attachment fields
        "acceptance_criteria": [], # Often kept in description or custom fields
        "status": status_name,
        "priority": priority_name,
        "sprint": "Active Sprint",
        "story_points": 5,
        "labels": fields.get("labels", []),
        "child_stories": child_stories
    }
    
    logger.info(
        f"[ingest_jira_epic] Loaded epic '{epic['summary']}' "
        f"with {len(epic['assets'])} assets and {len(epic['child_stories'])} child stories."
    )
    return epic


# ---------------------------------------------------------------------------
# Activity: Generate Spec v1
# ---------------------------------------------------------------------------

@activity.defn
async def generate_spec_v1(epic: Dict[str, Any]) -> str:
    """
    Step 2 — Write the initial Spec.md (v1) from the raw epic context (t0).
    """
    logger = activity.logger
    logger.info("[generate_spec_v1] Writing Spec.md v1 …")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Detect whether we're talking to a local or Cloud Temporal server
    api_key = os.environ.get("TEMPORAL_API_KEY", "")
    temporal_address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    if api_key:
        temporal_server_type = "☁️ Temporal Cloud"
    else:
        temporal_server_type = "🖥️ Local Temporal"

    assets_md = "\n".join(
        f"  - **{a['name']}** (`{a['type']}`) — {a['url']}"
        for a in epic.get("assets", [])
    )
    criteria_md = "\n".join(
        f"  - {c}" for c in epic.get("acceptance_criteria", [])
    )

    content = f"""# Workspace Spec — {epic['key']}: {epic['summary']}

> **Version:** v1  
> **Generated:** {now}  
> **Temporal Server:** {temporal_server_type} (`{temporal_address}`, namespace: `{temporal_namespace}`)  
> **Status:** {epic['status']}  
> **Priority:** {epic['priority']}  
> **Sprint:** {epic['sprint']}  
> **Story Points:** {epic['story_points']}  

---

## 1. Overview

{epic['description']}

---

## 2. Ingested Assets

{assets_md}

---

## 3. Acceptance Criteria

{criteria_md}

---

## 4. Labels

{', '.join(f'`{l}`' for l in epic.get('labels', []))}

---

## 5. Child Stories

{', '.join(epic.get('child_stories', []))}

---

## 6. Implementation Plan

1. **Analysis:** Epic `{epic['key']}` requires backend and infrastructural changes based on its acceptance criteria.
2. **Implementation Strategy:**
   - *Phase A:* Code scaffolding and database migrations.
   - *Phase B:* Core business logic and API endpoints.
   - *Phase C:* Comprehensive integration testing.
"""

    path = _spec_path()
    with open(path, "w") as f:
        f.write(content)

    logger.info(f"[generate_spec_v1] Spec.md v1 written to {path}")
    return path


# ---------------------------------------------------------------------------
# Activity: Agent Task 1 — Security Analysis
# ---------------------------------------------------------------------------

@activity.defn
async def run_security_analysis(epic: Dict[str, Any]) -> str:
    """
    Step 3a — Simulated agent: security & dependency analysis.
    Sleeps to mimic real inference time.
    """
    logger = activity.logger
    logger.info("[run_agent_task_1] Running security analysis agent …")
    await asyncio.sleep(2)  # simulate LLM / tool latency

    result = (
        f"**Security Analysis** (run at {datetime.utcnow().isoformat(timespec='seconds')}Z)\n\n"
        f"- Repo `{epic.get('key')}` scanned: 0 critical CVEs found.\n"
        f"- Dependency audit: all packages pinned, no known vulnerabilities.\n"
        f"- SAST scan complete: 2 low-severity findings flagged for review.\n"
        f"- Recommended action: enable Dependabot auto-merge for patch versions.\n"
    )
    logger.info("[run_agent_task_1] Security analysis complete.")
    return result


# ---------------------------------------------------------------------------
# Activity: Agent Task 2 — Architecture Review
# ---------------------------------------------------------------------------

@activity.defn
async def run_architecture_review(epic: Dict[str, Any]) -> str:
    """
    Step 3b — Simulated agent: architecture & scalability review.
    Sleeps to mimic real inference time.
    """
    logger = activity.logger
    logger.info("[run_agent_task_2] Running architecture review agent …")
    await asyncio.sleep(2)  # simulate LLM / tool latency

    result = (
        f"**Architecture Review** (run at {datetime.utcnow().isoformat(timespec='seconds')}Z)\n\n"
        f"- Service boundary analysis: microservice decomposition is well-structured.\n"
        f"- Data flow: stateless review pipeline identified; recommend adding a message queue for scale.\n"
        f"- PR throughput estimate: system can handle ~{epic.get('story_points', 30) * 50} reviews/day.\n"
        f"- Observability gap: no distributed tracing found; recommend adding OpenTelemetry.\n"
    )
    logger.info("[run_agent_task_2] Architecture review complete.")
    return result


# ---------------------------------------------------------------------------
# Activity: Update Spec v2
# ---------------------------------------------------------------------------

@activity.defn
async def update_spec_v2(agent_results: List[str], reviewer_comment: str = "") -> str:
    """
    Step 4 — Append agent task outputs + reviewer notes to produce Spec.md v2 (t0 + m).
    """
    logger = activity.logger
    logger.info("[update_spec_v2] Updating Spec.md to v2 …")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    path = _spec_path()
    with open(path, "r") as f:
        existing = f.read()

    # Patch the version header
    updated = existing.replace("> **Version:** v1", "> **Version:** v2")

    agent_section = f"""
---

## 6. Agent Task Results (v2 — {now})

"""
    for i, result in enumerate(agent_results, start=1):
        import re as _re
        match = _re.match(r'\*\*([^*]+)\*\*', result.strip())
        task_name = match.group(1) if match else f"Agent Task {i}"
        agent_section += f"### {task_name}\n\n{result}\n\n"

    if reviewer_comment:
        agent_section += (
            f"### 👤 Reviewer Notes\n\n"
            f"> {reviewer_comment}\n\n"
        )

    with open(path, "w") as f:
        f.write(updated + agent_section)

    logger.info(f"[update_spec_v2] Spec.md v2 written to {path}")
    return path


# ---------------------------------------------------------------------------
# Activity: Update Jira Comment
# ---------------------------------------------------------------------------

@activity.defn
async def update_jira_comment(epic_id: str, summary_comment: str) -> str:
    """
    Step 4b — Post a progress comment to the Jira issue.
    Uses the real Jira REST API when JIRA_API_TOKEN is set; falls back to mock.
    """
    logger = activity.logger
    logger.info(f"[update_jira_comment] Posting progress comment to Jira issue {epic_id} …")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    spec_ref = _spec_path()

    comment_text = (
        f"🤖 Automated Progress Update — {now}\n\n"
        f"{summary_comment}\n\n"
        f"📄 Full details in the generated spec: {spec_ref}"
    )

    if jira_client.jira_enabled():
        await jira_client.add_comment(epic_id, comment_text)
        logger.info(f"[update_jira_comment] ✅ Real Jira comment posted to {epic_id}")
    else:
        logger.info(f"[update_jira_comment] [MOCK] Jira comment:\n{comment_text}")

    return f"Jira comment posted to {epic_id} at {now}"


# ---------------------------------------------------------------------------
# Activity: Close Jira Issue
# ---------------------------------------------------------------------------

@activity.defn
async def close_jira_issue(epic_id: str, final_comment: str) -> str:
    """
    Step 5b — Post the final human approval comment and transition the Jira
    issue to 'Done'.
    Uses the real Jira REST API when JIRA_API_TOKEN is set; falls back to mock.
    """
    logger = activity.logger
    logger.info(f"[close_jira_issue] Closing Jira issue {epic_id} …")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    comment_text = (
        f"✅ Human Approval Received — {now}\n\n"
        f"{final_comment}\n\n"
        f"This issue is now being marked as Done."
    )

    if jira_client.jira_enabled():
        await jira_client.add_comment(epic_id, comment_text)
        transition_id = os.environ.get("JIRA_DONE_TRANSITION_ID", "")
        if transition_id:
            await jira_client.transition_issue(epic_id, transition_id)
            logger.info(f"[close_jira_issue] ✅ Jira issue {epic_id} transitioned to Done")
        else:
            logger.warning(
                "[close_jira_issue] JIRA_DONE_TRANSITION_ID not set — skipping transition. "
                "Run: python3 src/starter.py --jira-transitions <ISSUE_KEY> to find yours."
            )
    else:
        logger.info(f"[close_jira_issue] [MOCK] Jira close:\n{comment_text}")

    return f"Jira issue {epic_id} closed at {now}"


# ---------------------------------------------------------------------------
# Activity: Finalize Workspace
# ---------------------------------------------------------------------------

@activity.defn
async def finalize_workspace(epic_id: str, approver_comment: str) -> str:
    """
    Step 6 — Mark workspace as finalized after human approval.
    """
    logger = activity.logger
    logger.info(f"[finalize_workspace] Finalizing workspace for {epic_id} …")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    path = _spec_path()
    with open(path, "r") as f:
        existing = f.read()

    footer = (
        f"\n---\n\n"
        f"## ✅ Human Approval\n\n"
        f"- **Approved at:** {now}\n"
        f"- **Reviewer comment:** _{approver_comment}_\n"
        f"- **Workspace status:** FINALIZED\n\n"
        f"*This workspace lifecycle run is complete.*\n"
    )

    with open(path, "a") as f:
        f.write(footer)

    logger.info(f"[finalize_workspace] Workspace {epic_id} finalized. Spec.md updated.")
    return f"Workspace {epic_id} FINALIZED at {now}"


# ---------------------------------------------------------------------------
# Activity: Update Spec v3
# ---------------------------------------------------------------------------

@activity.defn
async def update_spec_v3(epic_id: str) -> str:
    """
    Step 7 — Fetch Jira development summary and append to Spec.md as v3.
    """
    logger = activity.logger
    logger.info(f"[update_spec_v3] Fetching Jira Development Summary for {epic_id} …")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Simulated Jira development data
    jira_dev_summary = (
        f"- **PRs Merged:** 2\n"
        f"- **Commits:** 14\n"
        f"- **CI/CD Build:** SUCCESS\n"
        f"- **Deployments:** Staging completed successfully.\n"
    )

    path = _spec_path()
    with open(path, "r") as f:
        existing = f.read()

    # Patch the version header
    updated = existing.replace("> **Version:** v2", "> **Version:** v3")

    summary_section = f"""
---

## 7. Jira Development Summary (v3 — {now})

{jira_dev_summary}
"""

    with open(path, "w") as f:
        f.write(updated + summary_section)

    logger.info(f"[update_spec_v3] Spec.md v3 written to {path}")
    return path
