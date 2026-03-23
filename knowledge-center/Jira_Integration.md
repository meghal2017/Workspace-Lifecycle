# Jira Integration — Knowledge Center

## Role
The Jira integration acts as the **data-access layer** for the workspace lifecycle workflow. It reads live Epic and Story data from Atlassian to drive a parallel agent execution pipeline.

---

## Key Files

| File | Purpose |
|---|---|
| `src/jira_client.py` | Core HTTP client for Jira REST API v3 |
| `src/activities.py` | Temporal activities for ingestion, commenting, and transitions |
| `src/setup_jira_demo.py` | Creates a live demo **Epic + Story** hierarchy in Jira |
| `src/cleanup_jira_workspace.py` | Wipes older issues from the project to maintain clarity |

---

## Hierarchy & Linkage
- **Structure**: We use a native **Epic -> Story** hierarchy.
- **Dynamic Discovery**: The `ingest_jira_epic` activity fetches the Epic and then discover its children using `jira_client.get_child_issues(epic_id)`.
- **Transitions**: The workflow automatically transitions subtasks to a configurable "In Progress" status when the agent begins its work loop.

---

## Communication Guidelines
To maintain high readability and "human-like" interactions:
1. **No Bot Boilerplate**: Avoid automated disclaimers like "Status Updated by Workflow".
2. **Dynamic Planning (`generate_subtask_plan`)**:
    - The agent analyzes the specific task summary (e.g., "UI: Build Profile Component") and the broader Epic description.
    - In **Offline Mode**, this uses the `src/scenarios.py` registry to provide consistent mock data for demonstration purposes.
    - It generates a list of realistic implementation steps (e.g., "Create React component", "Write HSL styles", "Add unit tests").
    - This plan is posted to Jira (or logged in offline mode) to provide a human-readable roadmap.
3. **Approval Stamps**: Every approved subtask resolution is stamped with a human approval comment for traceability.
4. **Spec Artifact**: The complete `Spec.md` content is posted as a markdown artifact comment on the Epic for a unified project view.

---

## Authentication
- Requires **Basic Auth**: `base64(email:api_token)`
- Token is generated at: [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
- Use `load_env(override=True)` to ensure local environment variables take precedence.

---

## Offline Mode
The system supports a **True Offline Mode** for development and demos when Jira is unavailable:
- **Trigger**: Set `JIRA_OFFLINE=true` or start the worker with the `--offline` flag.
- **Mock Ingestion**: `ingest_jira_epic` falls back to the `src/scenarios.py` registry, loading hardcoded Epics and Story hierarchies based on the provided ID (e.g., `profile`, `auth`, `search`).
- **Mock Interactions**: Commenting and transitions log `[MOCK]` indicators to the console instead of making API calls.

---

## Search API & ADF
- **JQL**: We use `/rest/api/3/search/jql` to discover issues.
- **Parsing**: `adf_to_text()` converts Atlassian Document Format (ADF) into markdown for agent ingestion. The parser currently focuses on block content (headings, paragraphs, lists).

---

## Known Issues / TODOs
- **ADF Complexity**: Tables and media in descriptions are currently ignored.
- **Pagination**: Search is currently limited to 100 results; needs offset support for massive projects.
- **Status Mapping**: Different Jira projects may use different transition IDs for "Done".
