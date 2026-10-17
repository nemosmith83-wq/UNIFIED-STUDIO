# Unified Studio build report

Build assembled on 2026-10-10 from the supplied project files.

## Version inventory and choice

| Input | What it contains | Decision |
| --- | --- | --- |
| `Unified_Studio_PUBLIC_MOBILE_v14_FINAL.zip` | Most complete app tree: authentication, responsive UI, backend, provider management, PromptVault Pro, tests, and mobile/LAN launcher. | Selected as the base. The app already integrates PromptVault and a guided RVC/Gradio workflow. |
| `Unified_Studio_FIXED_MOBILE_v13.zip` | Earlier app/backend; its PromptVault HTML is byte-identical to v14, but the main app and backend differ and are older. | Compared; not selected. |
| `Unified_Studio_FIXED_with_PromptVault_Pro_v13_FIXED (1).zip` | Earlier v13 app and a slightly older PromptVault HTML file. | Compared; not selected. |
| `TA_TRUE_OFFLINE_RELEASE_KIT_FIXED.zip` | Separate older local FastAPI/SQLite package with tests and a frontend, not the same v14 application tree. | Inspected as an alternate baseline; not merged because v14 already provides the more complete integrated interface. |
| `unified_studio_dashboard.html` | 42 KB visual project overview titled “Unified Studio — Project Overview Dashboard”; it describes v13 and is not the running app. | Inspected as a reference; not used as the application entry point. |
| PromptVault Pro v13 standalone HTML | 285,059 bytes; the integrated v14 PromptVault page is 285,216 bytes and already includes the newer bilingual RVC workflow. | v14 integrated copy retained. |
| PromptVault Pro v12 standalone HTML | 1,287,003 bytes, older standalone version. | Inspected; not substituted for the integrated v14 page. |
| `ultimate-rvc-main.zip` | 24 MB source archive for Ultimate RVC, MIT licensed; its README describes local Gradio, CLI, speech/song workflows, and a separate Python 3.12–3.13 environment. | Included with its extracted source under `optional/`; it is not installed or silently launched by Unified Studio. |
| `TA.rar` | 60-file/8-folder archive of an older Unified Studio copy; no distinct RVC model weights were identified in its listing. | Inspected; not merged. |

## What changed

- Added a **Perchance Resources** tab to the v14 UI with links to the verified AI Text Plugin, Text-to-Image Plugin, AI Story Generator, and AI RPG pages.
- Added a bilingual integration boundary page and a detailed Perchance report. Perchance links are user-initiated; the app does not automate the site or send data to it.
- Kept the existing PromptVault Pro RVC workflow. It accepts a Gradio URL entered by the user and embeds that service; it does not claim that the app itself trains or converts audio.
- Added the supplied Ultimate RVC source archive as an optional component, with its MIT license. Model weights were not present in the supplied archive.
- Kept the three uploaded standalone HTML references under `reference_inputs/` so the originals can be compared with the integrated build.
- Removed packaged test databases, SQLite files, bytecode caches, public-start tunnel helper, and generated test artifacts. The app creates a fresh local database on first run.
- Added a Docker/Compose cloud deployment profile with mounted persistent data/output volumes, configurable container port, a health endpoint, and a non-root runtime user.
- Made auth storage configurable, added interactive owner account creation, and added cloud flags to disable sign-up and code execution by default. Cloud mode forces HTTPS-only auth cookies.
- Changed the system status response to distinguish configured integrations from reachable services rather than reporting unverified providers as online.

## Integration limits and required external services

- Perchance's plugin pages document Perchance generator components. This review found no official standalone generation API, and the published Terms of Service prohibit scripted or bot access. No undocumented API calls or fake generation responses were added.
- PromptVault Pro's provider execution requires a user-supplied provider key. The main app's LLM/image features also depend on the providers configured in `.env`; offline chat requires the separately installed Ollama service and model.
- RVC requires a running RVC service and compatible model files. Use the optional source's instructions or another service you control, then paste its Gradio URL into PromptVault Pro. No trained `.pth`/`.index` voice model was included.
- The available upload record did not include `FINAL_ANDROID_PACK.zip` or `freellmapi-main.zip`. Neither was inspected or integrated; an Android package is not part of this build.

## Use

- Run `START.bat` for a local-only server at `127.0.0.1:5000`.
- `START_MOBILE.bat` binds to the local network for phone/tablet access and is intended only for a trusted private Wi-Fi/LAN. Do not port-forward it or use it as a public deployment.
- For phone/computer access over the internet, deploy with Docker using `CLOUD_DEPLOYMENT.md`; a hosting account, persistent storage, and HTTPS reverse proxy are required. No public URL was created in this build environment.
- Cloud safeguards reduce risk but do not amount to an independent security audit. Use one app replica; code execution remains disabled. There is no dependency lockfile, email verification, account recovery, or shared rate limiter. Configure external provider secrets in the host's secret manager.

## Validation

Validation completed: the no-network quick functional test passed (Windows output set to UTF-8), provider fallback test passed, JavaScript syntax check passed, Python AST syntax check passed for 134 Python files, and an in-process API smoke test passed for app entry, authentication gate, registration, protected route, Perchance guide page, and logout. The cloud configuration smoke passed for disabled sign-up, secure login cookies, authenticated status, and blocked code execution; Compose YAML parsed successfully. Docker image build/runtime checks could not run because Docker is not installed in this build environment. No external generation provider or RVC service was available, so their live generation flows were not run. The package is a web application, not an Android APK.
