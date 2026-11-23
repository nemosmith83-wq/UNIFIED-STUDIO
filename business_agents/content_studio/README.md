# Content Studio — AI Writing & Content Agent

A standalone Flask app for a small business editorial workflow. It combines the former AI Writing Studio and Content Agent into one role to avoid duplicated responsibilities.

## Features
- Editorial pipeline: Idea, Draft, Review, Published.
- Content records with channel, notes/body and scheduled date.
- AI outline and first-draft generation using an OpenAI-compatible Chat Completions endpoint.
- Published content and active brand guidelines are included as writing context.
- Weekly content plan generated every Monday at 09:00; daily queue summary logged at 17:30 (server timezone).
- Persistent SQLite database and activity log.
- Health endpoint at `/api/health`.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set OPENAI_API_KEY in your environment (AI writing requires it)
python app.py
```

Open http://localhost:8080. SQLite data is stored beside the app unless DATABASE_PATH is set.

## Docker

```bash
docker build -t content-studio-agent .
docker run -p 8080:8080 -v content-studio-data:/data --env-file .env content-studio-agent
```

Set `DATABASE_PATH=/data/content_studio.db` for persistent Docker storage. Keep API keys out of GitHub; use deployment environment secrets.
