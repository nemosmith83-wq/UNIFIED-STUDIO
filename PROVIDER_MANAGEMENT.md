# Unified Studio — Provider Management

Unified Studio now supports a configurable LLM provider layer.

## Providers

- Ollama — local HTTP API, no API key required.
- Groq — OpenAI-compatible chat completions endpoint.
- OpenRouter — OpenAI-compatible chat completions endpoint.
- Pollinations — OpenAI-compatible generation API.

Cloud providers are optional. An unconfigured provider is shown as **UNCONFIGURED** and is skipped during automatic fallback.

## Configuration

Copy `.env.example` to `.env` and set the credentials you intend to use.

```env
LLM_PROVIDER=ollama
LLM_FALLBACKS=groq,openrouter,pollinations

GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b

OPENROUTER_API_KEY=
OPENROUTER_MODEL=openai/gpt-oss-20b

POLLINATIONS_API_KEY=
POLLINATIONS_MODEL=openai
```

The application never returns API-key values through its provider-management API.

## UI

Open **Providers** in the left navigation.

The page provides:

- provider health/configuration status
- model and latency information
- explicit completion tests
- active-provider switching
- ordered fallback management
- fastest-healthy selection

## API

```text
GET  /api/providers/health
POST /api/providers/test
POST /api/providers/switch
GET  /api/providers/fallback
PUT  /api/providers/fallback
```

Provider management is separate from the image engines (`pollinations` and `stable_horde`) used by Image Lab and Comic Forge.
