# Jira Integration — Knowledge Center

## Role
The Jira integration acts as the **data-access layer** for the workspace lifecycle workflow. It reads live Epic/story data from Atlassian and feeds it into the Temporal activities so the agent pipeline operates on real project context.

---

## Key Files

| File | Purpose |
|---|---|
| `src/jira_client.py` | Core HTTP client for Jira REST API v3 |
| `src/activities.py` → `ingest_jira_epic()` | Temporal activity that calls jira_client |
| `src/setup_jira_demo.py` | Creates a live demo Epic + sub-tasks in Jira |
| `src/teardown_jira_demo.py` | Deletes a specific Epic and all linked children |
| `src/cleanup_jira_workspace.py` | Wipes ALL issues from the project (dangerous) |

---

## Authentication
- Atlassian requires **Basic Auth**: `base64(email:api_token)`
- To avoid stale tokens from bash sessions polluting the python env, all scripts call `load_dotenv(override=True)`.
- Token is generated at: https://id.atlassian.com/manage-profile/security/api-tokens
- The Atlassian account email and the API token **must belong to the same Atlassian account**. Mismatched logins cause 401 Unauthorized silently.

---

## Search API (Important!)
The Jira REST API `GET /rest/api/3/search` endpoint was **deprecated and now returns HTTP 410 Gone**.

**New endpoint:** `GET /rest/api/3/search/jql`

This endpoint only returns internal issue `id`s (not keys or fields). To hydrate the results, you must individually fetch each issue via `GET /rest/api/3/issue/{id}`.

```python
# Correct pattern (as implemented in search_issues):
ids = [i["id"] for i in r.json().get("issues", [])]
for issue_id in ids:
    full_issue = await get_issue(issue_id)  # returns key, fields, etc.
```

---

## Issue Linking (Demo Script)
The setup script creates a parent "Story" and links children via the **"Relates"** issue link type. This is NOT a strict Epic/Story hierarchy.

Because of this, the JQL query to find children must check **both** patterns:
```python
jql = f'parent = "{epic_key}" OR issue in linkedIssues("{epic_key}")'
```

Using only `parent = "{epic_key}"` will silently return zero results for generically linked issues, causing `teardown-demo` to skip child deletion.

---

## Agile Board / Sprint Integration
- Board and sprint IDs are fetched dynamically via `/rest/agile/1.0/board` and `/rest/agile/1.0/board/{id}/sprint`
- If no active sprint is found, the first future sprint is used.
- Sprint activation is attempted programmatically, but may require manual "Start Sprint" from the Jira UI in some project configurations.

---

## Known Issues / TODOs
- **Ingest activity fallback**: `ingest_jira_epic` in `activities.py` may still fall back to mock data in some paths. Needs investigation.
- **ADF Parsing**: The `adf_to_text()` parser handles basic blocks and text formatting, but complex ADF nodes (tables, media) are silently dropped.
- **Pagination**: `search_issues` currently fetches max 100 results. Projects with large backlogs will need pagination support.
