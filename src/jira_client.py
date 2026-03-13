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

def _auth_headers() -> Dict[str, str]:
    email = os.environ["JIRA_USER_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
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


async def get_issue(issue_key: str) -> Dict[str, Any]:
    """Fetch a Jira issue and return the raw JSON dict."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        return resp.json()


async def add_comment(issue_key: str, text: str) -> None:
    """Post a plain-text comment on a Jira issue."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}/comment"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers=_auth_headers(),
            json={"body": _adf_text(text)},
        )
        resp.raise_for_status()


async def get_transitions(issue_key: str) -> List[Dict[str, Any]]:
    """Return available workflow transitions for a Jira issue."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}/transitions"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        return resp.json().get("transitions", [])


async def transition_issue(issue_key: str, transition_id: str) -> None:
    """Transition a Jira issue (e.g. move to Done)."""
    url = f"{_base_url()}/rest/api/3/issue/{issue_key}/transitions"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers=_auth_headers(),
            json={"transition": {"id": transition_id}},
        )
        resp.raise_for_status()
