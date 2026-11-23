# Business Agents

Two independent, deployable business tools:

- [Content Studio](content_studio/) combines AI Writing Studio and Content Agent into one editorial workflow.
- [IT Support Agent](it_support_agent/) handles helpdesk tickets, triage, assets, fixes and known issues.

Both are Flask applications with SQLite persistence, Dockerfiles, environment examples, and scheduled background jobs. AI provider keys are runtime secrets and must never be committed.

## Run both together with Docker Compose

From this folder, set `OPENAI_API_KEY` in your shell or in an untracked `.env` file, then run:

`docker compose up --build -d`

Content Studio: http://localhost:8081
IT Support Agent: http://localhost:8082

Both databases are stored in named Docker volumes. Schedules use the container/server timezone. Content Studio creates a weekly plan Monday at 09:00 and a daily queue log at 17:30. IT Support creates an unresolved/aging report daily at 17:00.
