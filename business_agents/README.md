# Business Agents

Two independent, deployable business tools are stored here:

- `content_studio/` — AI Writing Studio and Content Agent combined into one editorial workflow.
- `it_support_agent/` — IT helpdesk intake, triage, assets and knowledge base.

Each folder has its own Flask application, dependencies, Dockerfile and environment example. Apps use SQLite for local persistence and APScheduler for scheduled jobs. Configure AI provider keys as runtime secrets; never commit them.
