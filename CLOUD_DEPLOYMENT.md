# Unified Studio: access it from anywhere

This build can run as a Docker container on a cloud host and serve the same responsive web app to phones and computers. A public URL is created by the hosting provider after you deploy it; this repository does not contain a hosting account or credentials, so it cannot publish that URL by itself.

## What works in this cloud build

- Unified Studio and the integrated PromptVault pages are served by the same app.
- Authentication database and generated files persist in Docker volumes.
- New account registration and the code execution endpoint are disabled by default in the cloud container.
- HTTPS cookie security is enabled for the cloud profile.
- Perchance is linked as a manual, separate-site handoff. No undocumented Perchance generation API or automated site access is used.
- RVC is an optional external service: connect a separately hosted RVC/Gradio endpoint in Voice Studio. The provided RVC source and assets do not include trained voice model weights or a public hosted inference service.

Text, image, and voice generation depend on configured external providers or separately running local services. An Ollama service on your own computer is not reachable from a cloud container by its `localhost` address. Configure a cloud provider key, use a reachable model service, or leave the relevant feature unavailable; the app must not report a fabricated generation result.

## Run on a Docker host

1. Install Docker Engine/Desktop on the host and copy the project folder there.
2. Copy `.env.cloud.example` to `.env.cloud`. Keep `.env.cloud` private and put real keys only in that file locally or the hosting provider's secret settings.
3. Start the app with `docker compose up -d --build`.
4. Create the first private account interactively with `docker compose exec studio python /app/backend/create_user.py`.
5. Put the service behind the provider's HTTPS reverse proxy, and open its HTTPS URL on any device. For a self-managed server, configure a domain and TLS reverse proxy before exposing the app publicly.

The included Compose file binds HTTP to loopback on host port `8080` by default so it is not directly reachable from the public internet. A reverse proxy on the same host can reach it at `127.0.0.1:8080` and provide HTTPS. Set `APP_HTTP_PORT` to change the host-side port for a self-managed setup. For a managed container platform, deploy the Dockerfile and let the platform's HTTPS proxy route to the container port.

Cloud platform deployment should use the included `Dockerfile` or Compose configuration, preserve `/app/data` and `/app/outputs` on persistent storage, and expose the container port selected by `PORT` (default `8000`). Configure provider secrets in the platform dashboard, set secure cookies to true, keep registration disabled, and retain code execution disabled. If the platform does not support persistent storage, account and output data can be lost on restart or redeploy.

## Accounts and access

With `ALLOW_REGISTRATION=false`, create each account from the host using the interactive command above. To allow open sign-up, change this variable to `true` only if that is intended, then redeploy. This app has no email verification or account recovery flow.

## Backups and rollback

Back up both Docker volumes (`studio_data` and `studio_outputs`) before upgrades. To roll back, stop the service and redeploy the last known image while retaining those volumes. Test restoration on a copy before relying on a backup.

## Known production limitations

- Authentication attempt limits and automation/workflow runtime state are in-process and not shared between multiple replicas. Run a single application replica unless those components are moved to shared storage/rate limiting.
- The local code runner is not a hardened OS sandbox. It is disabled in this cloud profile; enabling it on an internet-facing deployment requires a dedicated isolated execution service.
- User-supplied API keys in PromptVault are stored by the browser-side application. Use a trusted device and avoid shared browsers.
- The RVC source is provided as optional material, but hosting RVC inference requires separate compute, trained weights, and setup. It is not bundled into this lightweight web container.
- Perchance's terms restrict automated access. The integration therefore opens official plugin pages for manual use and does not proxy, scrape, or automate generation.

## Deployment checks

After deployment, verify the provider's HTTPS URL, log in, refresh the app, create and retrieve one output, and confirm that data remains after a container restart. A successful local container build is not proof that a cloud deployment or external generation provider is available.
