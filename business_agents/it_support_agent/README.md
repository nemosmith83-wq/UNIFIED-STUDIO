# IT Support Agent

A standalone Flask helpdesk app with ticket intake, AI triage, fix/known-issue knowledge, asset inventory and scheduled unresolved-ticket reports.

Features: ticket inbox with status/priority/owner/category; AI triage grounded in fixes and known issues; verified fix library; asset inventory; known issue workarounds; activity log; daily unresolved and 2+ day aging report at 17:00 server time; SQLite persistence; health endpoint at /api/health. Without an API key, ticket and knowledge workflows still work and triage clearly reports that AI is not configured.

## Local run

1. Install Python 3.11+.
2. Run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`, then set `OPENAI_API_KEY` to enable AI triage.
4. Run `python app.py` and open http://localhost:8080.

## Docker

Build with `docker build -t it-support-agent .`; run with `docker run -p 8080:8080 -v it-support-data:/data --env-file .env it-support-agent`. Keep `DATABASE_PATH=/data/it_support.db` for persistent storage. Never commit real API keys; configure them as deployment secrets.
