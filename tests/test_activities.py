"""
test_activities.py — Unit tests for activities, no Temporal server needed.
Calls activity functions directly as plain async functions.
"""
from __future__ import annotations

import asyncio
import json
import os
import pytest
import sys
import tempfile

# Point to src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_epic() -> dict:
    """Load the real mock Jira JSON as a dict, same shape activities receive."""
    data_path = os.path.join(
        os.path.dirname(__file__), "..", "mock_data", "jira_epic.json"
    )
    with open(data_path) as f:
        raw = json.load(f)

    # Massage assets to match the dataclass-serialised form (extra field)
    assets = []
    for a in raw.get("assets", []):
        extra = {k: v for k, v in a.items() if k not in ("asset_id", "type", "name", "url", "endpoint")}
        assets.append({
            "asset_id": a["asset_id"], "type": a["type"],
            "name": a["name"], "url": a.get("url", a.get("endpoint", "")), "extra": extra,
        })
    raw["assets"] = assets
    return raw


@pytest.fixture(autouse=True)
def use_tmp_specs(tmp_path, monkeypatch):
    """Redirect specs output to a tmp dir so tests don't pollute the real specs/ folder."""
    import activities as acts
    monkeypatch.setattr(acts, "_SPECS_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIngestJiraEpic:
    def test_returns_dict_with_expected_keys(self):
        from activities import ingest_jira_epic
        result = asyncio.run(ingest_jira_epic("EPIC-001"))
        assert isinstance(result, dict)
        assert result["id"] == "EPIC-001"
        assert "summary" in result
        assert "assets" in result
        assert len(result["assets"]) > 0

    def test_raises_on_wrong_epic_id(self):
        from activities import ingest_jira_epic
        with pytest.raises(ValueError, match="Epic ID mismatch"):
            asyncio.run(ingest_jira_epic("EPIC-999"))


class TestGenerateSpecV1:
    def test_creates_spec_file(self, sample_epic, tmp_path):
        from activities import generate_spec_v1
        path = asyncio.run(generate_spec_v1(sample_epic))
        assert os.path.exists(path)

    def test_spec_contains_v1_header(self, sample_epic, tmp_path):
        from activities import generate_spec_v1
        path = asyncio.run(generate_spec_v1(sample_epic))
        content = open(path).read()
        assert "**Version:** v1" in content
        assert sample_epic["summary"] in content

    def test_spec_contains_assets(self, sample_epic, tmp_path):
        from activities import generate_spec_v1
        path = asyncio.run(generate_spec_v1(sample_epic))
        content = open(path).read()
        for asset in sample_epic["assets"]:
            assert asset["name"] in content

    def test_spec_contains_ai_plan(self, sample_epic, tmp_path):
        from activities import generate_spec_v1
        path = asyncio.run(generate_spec_v1(sample_epic))
        content = open(path).read()
        assert "Implementation Plan" in content
        assert "Implementation Strategy" in content


class TestAgentTasks:
    def test_security_analysis_returns_string(self, sample_epic):
        from activities import run_security_analysis
        result = asyncio.run(run_security_analysis(sample_epic))
        assert isinstance(result, str)
        assert "Security Analysis" in result

    def test_architecture_review_returns_string(self, sample_epic):
        from activities import run_architecture_review
        result = asyncio.run(run_architecture_review(sample_epic))
        assert isinstance(result, str)
        assert "Architecture Review" in result

    async def test_both_tasks_run_in_parallel(self, sample_epic):
        """Both tasks should complete well under their combined serial time (4s)."""
        from activities import run_security_analysis, run_architecture_review
        import time
        start = time.monotonic()
        await asyncio.gather(
            run_security_analysis(sample_epic),
            run_architecture_review(sample_epic),
        )
        elapsed = time.monotonic() - start
        # Each sleeps 2s; parallel should be ~2s total, not 4s
        assert elapsed < 3.5, f"Tasks took {elapsed:.1f}s — expected ~2s in parallel"


class TestUpdateSpecV2:
    def test_upgrades_version_header(self, sample_epic, tmp_path):
        from activities import generate_spec_v1, update_spec_v2
        asyncio.run(generate_spec_v1(sample_epic))
        asyncio.run(update_spec_v2(["Result A", "Result B"]))
        content = open(os.path.join(str(tmp_path), "Spec.md")).read()
        assert "**Version:** v2" in content

    def test_appends_agent_results(self, sample_epic, tmp_path):
        from activities import generate_spec_v1, update_spec_v2
        asyncio.run(generate_spec_v1(sample_epic))
        asyncio.run(update_spec_v2(["Agent finding alpha", "Agent finding beta"]))
        content = open(os.path.join(str(tmp_path), "Spec.md")).read()
        assert "Agent finding alpha" in content
        assert "Agent finding beta" in content


class TestFinalizeWorkspace:
    def test_appends_approval_footer(self, sample_epic, tmp_path):
        from activities import generate_spec_v1, update_spec_v2, finalize_workspace
        asyncio.run(generate_spec_v1(sample_epic))
        asyncio.run(update_spec_v2(["A"], "B"))
        asyncio.run(finalize_workspace(sample_epic["id"], "Ready to ship"))
        content = open(os.path.join(str(tmp_path), "Spec.md")).read()
        assert "Ready to ship" in content
        assert "FINALIZED" in content

class TestUpdateSpecV3:
    def test_appends_jira_summary(self, sample_epic, tmp_path):
        from activities import generate_spec_v1, update_spec_v2, update_spec_v3
        asyncio.run(generate_spec_v1(sample_epic))
        asyncio.run(update_spec_v2(["Agent finding alpha"]))
        asyncio.run(update_spec_v3(sample_epic["id"]))
        content = open(os.path.join(str(tmp_path), "Spec.md")).read()
        assert "**Version:** v3" in content
        assert "Jira Development Summary" in content
        assert "PRs Merged" in content
