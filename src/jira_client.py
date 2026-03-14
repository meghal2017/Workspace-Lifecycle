"""
jira_client.py — Thin async Jira REST API v3 client.

Reads credentials from environment variables:
    JIRA_BASE_URL          e.g. https://meghaldiscover.atlassian.net
    JIRA_USER_EMAIL        your Atlassian account email
    JIRA_API_TOKEN         API token from id.atlassian.com
    JIRA_PROJECT_KEY       project key prefix, e.g. WL
    JIRA_DONE_TRANSITION_ID  numeric transition ID for "Done"

All methods raise httpx.HTTPStatusError on non-2xx responses.
"""
from __future__ import annotations

import base64
import os
from typing import Any, Dict, List, Optional

import httpx

# ---------------------------------------------------------------------------
# Credentials helpers
# ---------------------------------------------------------------------------

def _base_url() -> str:
    return os.environ.get("JIRA_BASE_URL", "").rstrip("/")

def _auth_tuple() -> tuple:
    email = os.environ["JIRA_USER_EMAIL"].strip()
    token = os.environ["JIRA_API_TOKEN"].strip()
    return (email, token)

def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def jira_enabled() -> bool:
    """Return True when all required Jira env vars are present."""
    return all(
        os.environ.get(k)
        for k in ("JIRA_BASE_URL", "JIRA_USER_EMAIL", "JIRA_API_TOKEN")
    )


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _adf_text(text: str) -> Dict[str, Any]:
    """Wrap a plain text string in Atlassian Document Format (ADF)."""
    paragraphs = []
    for line in text.split("\n"):
        paragraphs.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": line or " "}],
        })
    return {"type": "doc", "version": 1, "content": paragraphs}


def adf_to_text(adf: Optional[Dict[str, Any]]) -> str:
    """Parse a Jira ADF document back to a simplified plain text/markdown string."""
    if not adf or adf.get("type") != "doc":
        return ""
    
    lines = []
    for block in adf.get("content", []):
        block_type = block.get("type")
        if block_type in ("paragraph", "heading"):
            node_text = ""
            for node in block.get("content", []):
                if node.get("type") == "text":
                    text = node.get("text", "")
                    # Add simple markdown formatting for bold/italic if present
                    marks = [m.get("type") for m in node.get("marks", [])]
                    if "strong" in marks:
                        text = f"**{text}**"
                    if "em" in marks:
                        text = f"*{text}*"
                    node_text += text
                elif node.get("type") == "hardBreak":
                    node_text += "\n"
            
            if block_type == "heading":
                level = block.get("attrs", {}).get("level", 1)
                lines.append(f"{'#' * level} {node_text}\n")
            else:
                lines.append(f"{node_text}\n")
        elif block_type == "bulletList" or block_type == "orderedList":
            # Simplified list rendering
            for i, li in enumerate(block.get("content", [])):
                if li.get("type") == "listItem":
                    # Just grab text from the first paragraph of the list item
                    li_text = ""
                    for li_content in li.get("content", []):
                        if li_content.get("type") == "paragraph":
                            for node in li_content.get("content", []):
                                if node.get("type") == "text":
                                    li_text += node.get("text", "")
                    
                    prefix = "- " if block_type == "bulletList" else f"{i+1}. "
                    lines.append(f"{prefix}{li_text}")
            lines.append("")
        elif block_type == "rule":
            lines.append("---\n")
            
    return "\n".join(lines).strip()


async def get_issue(issue_key: str) -> Dict[str, Any]:
    """Fetch a Jira issue and return the raw JSON dict."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}"
    async with httpx.AsyncClient(auth=_auth_tuple()) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def search_issues(jql: str) -> List[Dict[str, Any]]:
    """Search for issues using JQL."""
    url = f"{_base_url()}/rest/api/3/search/jql"
    async with httpx.AsyncClient(auth=_auth_tuple()) as client:
        resp = await client.get(url, headers=_headers(), params={"jql": jql, "maxResults": 100})
        resp.raise_for_status()
        
        # New API only returns IDs
        ids = [i["id"] for i in resp.json().get("issues", [])]
        
        issues = []
        for issue_id in ids:
            issue_data = await get_issue(issue_id)
            issues.append(issue_data)
            
        return issues


async def get_child_issues(epic_key: str) -> List[Dict[str, Any]]:
    """Fetch the child issues (stories/tasks) belonging to an Epic."""
    jql = f'parent = "{epic_key}" OR issue in linkedIssues("{epic_key}")'
    return await search_issues(jql)


async def delete_issue(issue_key: str) -> None:
    """Delete a Jira issue."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}"
    async with httpx.AsyncClient(auth=_auth_tuple()) as client:
        resp = await client.delete(url, headers=_headers())
        resp.raise_for_status()


async def create_issue(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Jira issue with the given fields."""
    url = f"{_base_url()}/rest/api/3/issue"
    async with httpx.AsyncClient(auth=_auth_tuple()) as client:
        resp = await client.post(url, headers=_headers(), json={"fields": fields})
        resp.raise_for_status()
        return resp.json()


async def link_issue(inward_key: str, outward_key: str, link_type_name: str = "Relates") -> None:
    """Create an issue link between two issues."""
    url = f"{_base_url()}/rest/api/3/issueLink"
    payload = {
        "type": {"name": link_type_name},
        "inwardIssue": {"key": inward_key},
        "outwardIssue": {"key": outward_key}
    }
    async with httpx.AsyncClient(auth=_auth_tuple()) as client:
        resp = await client.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()


async def add_comment(issue_key: str, text: str) -> None:
    """Post a plain-text comment on a Jira issue."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}/comment"
    async with httpx.AsyncClient(auth=_auth_tuple()) as client:
        resp = await client.post(
            url,
            headers=_headers(),
            json={"body": _adf_text(text)},
        )
        resp.raise_for_status()


async def get_transitions(issue_key: str) -> List[Dict[str, Any]]:
    """Return available workflow transitions for a Jira issue."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}/transitions"
    async with httpx.AsyncClient(auth=_auth_tuple()) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.json().get("transitions", [])


async def transition_issue(issue_key: str, transition_id: str) -> None:
    """Transition a Jira issue (e.g. move to Done)."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}/transitions"
    async with httpx.AsyncClient(auth=_auth_tuple()) as client:
        resp = await client.post(
            url,
            headers=_headers(),
            json={"transition": {"id": transition_id}},
        )
        resp.raise_for_status()


async def _find_transition(issue_key: str, target_states: List[str]) -> Optional[str]:
    """Return the ID of the first available transition matching the target states."""
    transitions = await get_transitions(issue_key)
    target_states_lower = [s.lower() for s in target_states]
    
    for t in transitions:
        name = t.get("name", "").lower()
        if any(target in name for target in target_states_lower):
            return t["id"]
    return None


async def transition_to_in_progress(issue_key: str) -> bool:
    """Attempt to transition an issue to an active 'In Progress' state.
    Returns True if successfully transitioned, False if no matching transition was found.
    """
    targets = ["in progress", "start progress", "active", "doing", "open"]
    transition_id = await _find_transition(issue_key, targets)
    if not transition_id:
        return False
        
    await transition_issue(issue_key, transition_id)
    return True


async def transition_to_done(issue_key: str) -> bool:
    """Attempt to transition an issue to a terminal 'Done' state.
    Returns True if successfully transitioned, False if no matching transition was found.
    """
    targets = ["done", "closed", "resolved", "completed"]
    transition_id = await _find_transition(issue_key, targets)
    if not transition_id:
        return False
        
    await transition_issue(issue_key, transition_id)
    return True
