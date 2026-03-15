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
2. **Dynamic Plans**: Implementation plans are generated at runtime by the agent. They are NOT stored in the demo data.
3. **Approval Stamps**: Every approved subtask resolution is stamped with a human approval comment for traceability.
4. **Spec Artifact**: The complete `Spec.md` content is posted as a markdown artifact comment on the Epic for a unified project view.

---

## Authentication
- Requires **Basic Auth**: `base64(email:api_token)`
- Token is generated at: [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
- Use `load_env(override=True)` to ensure local environment variables take precedence.

---

## Search API & ADF
- **JQL**: We use `/rest/api/3/search/jql` to discover issues.
- **Parsing**: `adf_to_text()` converts Atlassian Document Format (ADF) into markdown for agent ingestion. The parser currently focuses on block content (headings, paragraphs, lists).

---

## Known Issues / TODOs
- **ADF Complexity**: Tables and media in descriptions are currently ignored.
- **Pagination**: Search is currently limited to 100 results; needs offset support for massive projects.
- **Status Mapping**: Different Jira projects may use different transition IDs for "Done".
