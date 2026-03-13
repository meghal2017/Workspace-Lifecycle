# Security Analysis Agent

## Role
The Security Analysis agent (currently simulated in `src/activities.py` as `run_security_analysis`) is responsible for analyzing the Jira Epic and determining any potential security vulnerabilities, dependency risks, or required compliance checks before development officially begins.

## Current Structure
- **Trigger Phase:** Phase 3 of the Temporal Workflow (runs in parallel with Architecture Review).
- **Execution:** Runs as a standard Temporal `@activity.defn`. 
- **Input:** Takes the full serialized Jira Epic context (Dictionary).
- **Output:** Returns a Markdown-formatted string summarizing CVEs, Dependabot audits, and Static Application Security Testing (SAST) findings.

## Learnings & Useful Context
- **Tooling:** In a real implementation, this agent would likely need API access to GitHub Advanced Security, Snyk, or SonarQube to pull real CVE data.
- **Latency:** Because this agent interacts with external security scanners, its Temporal activity MUST have a generous `schedule_to_close_timeout` and appropriate retry policies to handle third-party rate limits.
