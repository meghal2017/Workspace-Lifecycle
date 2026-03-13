"""
mock_jira.py — Loads the dummy Jira Epic from JSON and returns typed dataclasses.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class JiraAsset:
    asset_id: str
    type: str
    name: str
    url: str = ""  # optional — some asset types use a different field (e.g. endpoint)
    extra: dict = field(default_factory=dict)


@dataclass
class JiraEpic:
    id: str
    key: str
    summary: str
    description: str
    status: str
    priority: str
    reporter: str
    assignee: str
    labels: List[str]
    story_points: int
    sprint: str
    assets: List[JiraAsset]
    acceptance_criteria: List[str]
    child_stories: List[str]


def load_jira_epic(epic_id: str = "EPIC-001") -> JiraEpic:
    """
    Load the mock Jira Epic that matches the given epic_id.
    Reads from mock_data/jira_epic.json relative to the project root.
    """
    data_path = os.path.join(
        os.path.dirname(__file__), "..", "mock_data", "jira_epic.json"
    )
    with open(os.path.abspath(data_path), "r") as f:
        raw = json.load(f)

    if raw["id"] != epic_id:
        raise ValueError(f"Epic ID mismatch: expected {epic_id}, got {raw['id']}")

    assets = []
    for a in raw.get("assets", []):
        extra = {k: v for k, v in a.items() if k not in ("asset_id", "type", "name", "url", "endpoint")}
        assets.append(JiraAsset(
            asset_id=a["asset_id"],
            type=a["type"],
            name=a["name"],
            url=a.get("url", a.get("endpoint", "")),
            extra=extra,
        ))

    return JiraEpic(
        id=raw["id"],
        key=raw["key"],
        summary=raw["summary"],
        description=raw["description"],
        status=raw["status"],
        priority=raw["priority"],
        reporter=raw["reporter"],
        assignee=raw["assignee"],
        labels=raw["labels"],
        story_points=raw["story_points"],
        sprint=raw["sprint"],
        assets=assets,
        acceptance_criteria=raw["acceptance_criteria"],
        child_stories=raw["child_stories"],
    )
