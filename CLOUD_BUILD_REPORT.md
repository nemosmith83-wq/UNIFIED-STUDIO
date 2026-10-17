# Cloud-ready build report — 2026-10-10

## Included

- Unified Studio + PromptVault + the previously verified manual Perchance handoff.
- Docker image definition and Compose deployment with persistent storage for SQLite databases and generated files.
- Container health endpoint, configurable platform port, non-root container user, and cloud defaults that require HTTPS cookies, disable public registration, and disable the non-isolated code runner.
- Interactive account creation command for the owner when public registration is disabled.
- Optional RVC source remains separate. It needs its own model weights, compute, and hosted inference endpoint before voice conversion is available remotely.

## Checks run

- Cloud configuration smoke against FastAPI TestClient: passed. Checked health, disabled registration, secure login cookie, authenticated status, and both disabled code execution routes.
- Provider management test: passed.
- Quick function test: passed (run with UTF-8 terminal output).
- Python syntax compilation for changed backend files: passed.
- Frontend JavaScript syntax check: passed.
- Compose YAML parse: passed.
- Docker image build and runtime health check: not run because Docker is not installed in the build environment.
- Public cloud deployment: not performed. No hosting account, project, domain, or deployment credentials were provided. The final public URL must come from the chosen cloud host.

## Operational limitations

Deploy one app replica with durable volumes at `/app/data` and `/app/outputs`. The current authentication throttling and automation/workflow runtime state are process-local. Keep code execution disabled for public hosting. See `CLOUD_DEPLOYMENT.md` for setup and rollback steps.
