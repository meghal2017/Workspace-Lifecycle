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
    child_stories = []
    for child in child_issues:
        c_fields = child.get('fields', {})
        c_desc = jira_client.adf_to_text(c_fields.get('description'))
        
        child_stories.append({
            "key": child['key'], 
            "summary": c_fields.get('summary', ''),
            "description": c_desc
        })
    
    # Note: Transitioning to "In Progress" now happens dynamically later in the parallel workflow for each subtask
    
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

{', '.join(epic.get('child_stories_fmt', [s['key'] + ' - ' + s['summary'] for s in epic.get('child_stories', [])]))}

---

## 6. Implementation Plan

"""
    # Build hierarchical plan mapping to child tasks
    for s in epic.get('child_stories', []):
        key = s['key']
        summ = s['summary']
        content += f"### Tasks for {key}: {summ}\n"
        content += f"- [ ] Analyze requirements for {summ}\n"
        content += f"- [ ] Implement core logic and file changes\n"
        content += f"- [ ] Run local verification suite\n\n"

    path = _spec_path()
    with open(path, "w") as f:
        f.write(content)

    logger.info(f"[generate_spec_v1] Spec.md v1 written to {path}")
    return path


# ---------------------------------------------------------------------------
# Activity: Generate Subtask Plan
# ---------------------------------------------------------------------------

@activity.defn
async def generate_subtask_plan(subtask_id: str, summary: str, epic_context: str) -> List[str]:
    """
    Simulated reasoning: Agent analyzes the subtask and epic context to generate a local plan.
    """
    activity.logger.info(f"[generate_subtask_plan] Agent planning for {subtask_id} …")
    await asyncio.sleep(1) # simulate reasoning
    
    # Simple heuristic-based plan generation for the POC
    s = summary.lower()
    if "ui" in s or "component" in s:
        return [
            f"Analyze design specs for {summary}",
            "Implement responsive UI components",
            "Verify accessibility and styling"
        ]
    elif "backend" in s or "api" in s or "endpoint" in s:
        return [
            f"Define data models for {summary}",
            "Implement business logic and service layer",
            "Expose REST/GraphQL endpoints"
        ]
    elif "test" in s or "cypress" in s or "unit" in s:
        return [
            f"Identify test cases for {summary}",
            "Implement automated test scripts",
            "Verify coverage and edge cases"
        ]
    elif "infra" in s or "deploy" in s or "vector" in s:
        return [
            f"Review resource requirements for {summary}",
            "Provision cloud infrastructure",
            "Validate service connectivity"
        ]
    else:
        return [
            f"Research requirements for {summary}",
            "Implement the requested logic",
            "Perform local verification"
        ]

# ---------------------------------------------------------------------------
# Activity: Execute Agent Resolution
# ---------------------------------------------------------------------------

@activity.defn
async def execute_agent_resolution(subtask_id: str, summary: str, plan_steps: List[str] = None) -> str:
    """
    Simulated agent processing a specific subtask.
    """
    logger = activity.logger
    logger.info(f"[execute_agent_resolution] Agent working on {subtask_id}: {summary} …")
    
    if jira_client.jira_enabled():
        await jira_client.transition_to_in_progress(subtask_id)
        
    await asyncio.sleep(2)  # simulate LLM latency

    plan_md = ""
    if plan_steps:
        plan_md = "### Implementation Approach\n" + "\n".join([f"- {step}" for step in plan_steps]) + "\n\n"

    result = (
        f"**Resolution for {subtask_id}**\n\n"
        f"{plan_md}"
        f"### Results summary\n"
        f"Agent processed request: `{summary}`\n"
        f"- Implemented necessary file changes.\n"
        f"- Ran unit test suite locally: All tests passed.\n"
    )
    logger.info(f"[execute_agent_resolution] Agent `{subtask_id}` complete.")
    return result


# ---------------------------------------------------------------------------
# Activity: Update Spec v2
# ---------------------------------------------------------------------------

@activity.defn
async def update_spec_v2(agent_results: List[str]) -> str:
    """
    Step 4 — Append combined agent task results to produce Spec.md v2.
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

## 7. Parallel Subtask Resolutions (v2 — {now})

"""
    for res in agent_results:
        agent_section += f"{res}\n\n---\n\n"

    with open(path, "w") as f:
        f.write(updated + agent_section)

    logger.info(f"[update_spec_v2] Spec.md v2 written to {path}")
    return path

    logger.info(f"[update_spec_v2] Spec.md v2 written to {path}")
    return path


# ---------------------------------------------------------------------------
# Activity: Update Jira Comment
# ---------------------------------------------------------------------------

@activity.defn
async def update_jira_comment(issue_id: str, summary_comment: str) -> str:
    """
    Step 4b — Post a progress comment to a specific Jira issue.
    Uses the real Jira REST API when JIRA_API_TOKEN is set; falls back to mock.
    """
    logger = activity.logger
    logger.info(f"[update_jira_comment] Posting progress comment to Jira issue {issue_id} …")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    spec_ref = _spec_path()

    comment_text = (
        f"{summary_comment}\n\n"
        f"📄 Full details in the generated spec: {spec_ref}"
    )

    if jira_client.jira_enabled():
        # Comment on the specified issue
        await jira_client.add_comment(issue_id, comment_text)
        logger.info(f"[update_jira_comment] ✅ Real Jira comment posted to {issue_id}")
    else:
        logger.info(f"[update_jira_comment] [MOCK] Jira comment for {issue_id}:\n{comment_text}")

    return f"Jira comment posted to {issue_id} at {now}"


# ---------------------------------------------------------------------------
# Activity: Close Jira Issue
# ---------------------------------------------------------------------------

@activity.defn
async def close_jira_issue(issue_id: str, final_comment: str) -> str:
    """
    Post a final human approval comment and transition the specific Jira issue to 'Done'.
    """
    logger = activity.logger
    logger.info(f"[close_jira_issue] Closing Jira issue {issue_id} …")
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    comment_text = (
        f"{final_comment}\n\n"
        f"This issue is now marked as Done."
    )

    if jira_client.jira_enabled():
        await jira_client.add_comment(issue_id, comment_text)
        success = await jira_client.transition_to_done(issue_id)
        if success:
            logger.info(f"[close_jira_issue] ✅ Jira Issue {issue_id} transitioned to Done")
        else:
            logger.warning(f"[close_jira_issue] ⚠️ Could not find a 'Done' transition for {issue_id}")
    else:
        logger.info(f"[close_jira_issue] [MOCK] Jira close for {issue_id}:\n{comment_text}")

    return f"Jira issue {issue_id} closed at {now}"


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

    logger.info(f"[finalize_workspace] Workspace for {epic_id} sealed and finalized.")
    return f"Workspace for {epic_id} successfully finalized."

# ---------------------------------------------------------------------------
# Activity: Post Implementation Plan to Jira
# ---------------------------------------------------------------------------

@activity.defn
async def post_implementation_plan(epic_id: str, spec_path: str) -> None:
    """Read the To-Do list from Spec.md and post it as a comment on the Epic."""
    if not jira_client.jira_enabled(): return

    try:
        with open(spec_path, "r") as f:
            content = f.read()
        
        # Extract Section 6 (To-Do List)
        if "## 6. Implementation Plan" in content:
            todo_section = content.split("## 6. Implementation Plan")[1].strip()
            comment = f"📝 **Implementation Plan (To-Do List)**\n\n{todo_section}"
            await jira_client.add_comment(epic_id, comment)
            activity.logger.info(f"[post_implementation_plan] Plan posted to {epic_id}")
    except Exception as e:
        activity.logger.warning(f"[post_implementation_plan] Failed to post plan: {e}")

# ---------------------------------------------------------------------------
# Activity: Post Full Spec Artifact to Jira
# ---------------------------------------------------------------------------

@activity.defn
async def post_spec_artifact(epic_id: str, spec_path: str) -> None:
    """Post the entire Spec.md file content as a markdown comment artifact."""
    if not jira_client.jira_enabled(): return

    try:
        with open(spec_path, "r") as f:
            content = f.read()
        
        artifact_block = f"📂 **Spec.md Full Artifact Repository**\n\n{content}"
        await jira_client.add_comment(epic_id, artifact_block)
        activity.logger.info(f"[post_spec_artifact] Full spec artifact posted to {epic_id}")
    except Exception as e:
        activity.logger.warning(f"[post_spec_artifact] Failed to post artifact: {e}")


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
