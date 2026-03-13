# Architecture Review Agent

## Role
The Architecture Review agent (currently simulated in `src/activities.py` as `run_architecture_review`) is responsible for reading the context of a Jira Epic and analyzing the system design implications. It evaluates service boundaries, data flows, scalability bottlenecks, and observability gaps.

## Current Structure
- **Trigger Phase:** Phase 3 of the Temporal Workflow (runs in parallel with Security Analysis).
- **Execution:** Runs as a standard Temporal `@activity.defn`.
- **Input:** Takes the full serialized Jira Epic context (Dictionary).
- **Output:** Returns a Markdown-formatted string containing the architectural assessment.

## Learnings & Useful Context
- **Context Window:** To make this agent real, it will require immense context. Passing just the Jira ticket will not be enough; it will need RAG capabilities or vector search access to the company's existing Architecture Decision Records (ADRs) and codebase repositories.
- **Parallel Execution:** It currently runs concurrently with the Security Agent using `asyncio.gather`. If it ever needs to rely on the *output* of the Security Agent, this structural parallel execution in `workflow.py` will need to be refactored into a sequential chain.
