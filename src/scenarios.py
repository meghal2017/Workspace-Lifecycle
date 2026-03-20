"""
scenarios.py — A central registry of demo scenarios (Epics + Child Stories).
Used by both the setup script (to create real Jira issues) and the worker 
(to simulate ingestion in Offline Mode).
"""

SCENARIOS = {
    "profile": {
        "summary": "Feature: User Profile Management",
        "description": "As a user, I want to manage my personal information, notification preferences, and billing details in one place.",
        "acceptance_criteria": [
            "User can view their avatar, name, and email.",
            "User can update notification toggles (Email/SMS).",
            "Billing history displays a list of recent transactions.",
            "Mobile-responsive design across all breakpoints."
        ],
        "labels": ["frontend", "profile", "v1.0"],
        "children": [
            {
                "summary": "UI: Build Profile React Component",
                "desc": "Develop the React frontend with state management for profile forms."
            },
            {
                "summary": "Backend: Add GET/PUT /api/user/profile Endpoints",
                "desc": "Implement Node.js/Python endpoints with database integration."
            },
            {
                "summary": "Testing: E2E Cypress Tests for Profile",
                "desc": "Automated regression suite for name updates and validation errors."
            }
        ]
    },
    "auth": {
        "summary": "Security: Multi-Factor Authentication (MFA)",
        "description": "Improve platform security by implementing Time-based One-Time Password (TOTP) for all administrative accounts.",
        "acceptance_criteria": [
            "Enable TOTP secret generation via QR code.",
            "Enforce MFA challenge on login for 'Admin' role.",
            "Provide backup recovery codes for users.",
            "Audit logs must record all MFA enablement events."
        ],
        "labels": ["security", "auth", "critical"],
        "children": [
            {
                "summary": "Logic: TOTP Secret Generation & QR API",
                "desc": "Implement the core vault logic for secret storage and QR code generation."
            },
            {
                "summary": "UI: MFA Setup & Verification Screens",
                "desc": "Design the setup flow and the challenge prompt UI."
            },
            {
                "summary": "Audit: Integration with Security Logs",
                "desc": "Ensure all MFA attempts are logged for compliance monitoring."
            }
        ]
    },
    "search": {
        "summary": "Platform: Semantic Product Search",
        "description": "Replace existing keyword search with a vector-based semantic search to improve discovery relevance.",
        "acceptance_criteria": [
            "Support natural language queries (e.g., 'warm winter gear').",
            "Latency must remain under 200ms for 95th percentile.",
            "Integrate with Pinecone/Milvus vector database.",
            "Highlight relevant keywords in search results."
        ],
        "labels": ["platform", "search", "ai"],
        "children": [
            {
                "summary": "Infra: Provision Vector DB & Indexing",
                "desc": "Set up the vector database and pipeline for product indexing."
            },
            {
                "summary": "Model: Deploy Embedding Inference Service",
                "desc": "Host the NLP model to convert queries into vectors."
            },
            {
                "summary": "UI: New Search Results Layout",
                "desc": "Build a modern masonry-style grid for displayed products."
            }
        ]
    }
}
