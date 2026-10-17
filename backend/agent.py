"""
agent.py — Unified multi-agent AI system.
Routes requests to specialists: web_search, code, image, general.
Uses Ollama (LOCAL, 100% FREE, NO API KEY).
"""

import os
import json
import requests
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

import memory as mem
import tools

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# LLM Provider Management
# ─────────────────────────────────────────────────────────────────────────────

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
LLM_FALLBACKS = [
    item.strip().lower()
    for item in os.getenv("LLM_FALLBACKS", "groq,openrouter,pollinations").split(",")
    if item.strip()
]

PROVIDERS = {
    "ollama": {
        "name": "Ollama",
        "kind": "local",
        "base_url": os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        "model": os.getenv("OLLAMA_MODEL", "mistral"),
        "api_key_env": None,
        "default_model": "mistral",
    },
    "groq": {
        "name": "Groq",
        "kind": "openai_compatible",
        "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        "api_key_env": "GROQ_API_KEY",
        "default_model": "openai/gpt-oss-20b",
    },
    "openrouter": {
        "name": "OpenRouter",
        "kind": "openai_compatible",
        "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
        "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b"),
        "api_key_env": "OPENROUTER_API_KEY",
        "default_model": "openai/gpt-oss-20b",
    },
    "pollinations": {
        "name": "Pollinations",
        "kind": "openai_compatible",
        "base_url": os.getenv("POLLINATIONS_BASE_URL", "https://gen.pollinations.ai/v1").rstrip("/"),
        "model": os.getenv("POLLINATIONS_MODEL", "openai"),
        "api_key_env": "POLLINATIONS_API_KEY",
        "default_model": "openai",
    },
}

LAST_PROVIDER_USED = LLM_PROVIDER
LAST_PROVIDER_FALLBACKS: List[str] = []
LAST_PROVIDER_ERROR = ""


def _parse_provider_chain(raw: str, exclude: Optional[str] = None) -> List[str]:
    result = []
    for name in raw.split(","):
        provider = name.strip().lower()
        if provider in PROVIDERS and provider != exclude and provider not in result:
            result.append(provider)
    return result


def _provider_configured(provider: str) -> bool:
    cfg = PROVIDERS[provider]
    if cfg["kind"] == "local":
        return True
    env_name = cfg.get("api_key_env")
    return bool(os.getenv(env_name or "", "").strip())


def _provider_headers(provider: str) -> Dict[str, str]:
    cfg = PROVIDERS[provider]
    headers = {"Content-Type": "application/json"}
    env_name = cfg.get("api_key_env")
    if env_name:
        key = os.getenv(env_name, "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
    if provider == "openrouter":
        app_url = os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:5000").strip()
        app_title = os.getenv("OPENROUTER_X_TITLE", "Unified Studio").strip()
        if app_url:
            headers["HTTP-Referer"] = app_url
        if app_title:
            headers["X-Title"] = app_title
    return headers


def _call_ollama(provider: str, messages: List[Dict], max_tokens: int, temperature: float) -> str:
    cfg = PROVIDERS[provider]
    response = requests.post(
        f"{cfg['base_url']}/api/chat",
        json={
            "model": cfg["model"],
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    content = data.get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Provider returned an empty response")
    return content.strip()


def _call_openai_compatible(provider: str, messages: List[Dict], max_tokens: int, temperature: float) -> str:
    cfg = PROVIDERS[provider]
    if not _provider_configured(provider):
        raise RuntimeError(f"{cfg['name']} is not configured: set {cfg['api_key_env']}")
    response = requests.post(
        f"{cfg['base_url']}/chat/completions",
        headers=_provider_headers(provider),
        json={
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"{cfg['name']} returned an unexpected response") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Provider returned an empty response")
    return content.strip()


def _call_provider(provider: str, messages: List[Dict], max_tokens: int, temperature: float) -> str:
    if provider not in PROVIDERS:
        raise RuntimeError(f"Unsupported LLM provider: {provider}")
    cfg = PROVIDERS[provider]
    if cfg["kind"] == "local":
        return _call_ollama(provider, messages, max_tokens, temperature)
    return _call_openai_compatible(provider, messages, max_tokens, temperature)


def _llm(messages: List[Dict], max_tokens: int = 2000, temperature: float = 0.7) -> str:
    """Call the selected LLM and walk the configured fallback chain on failure."""
    global LAST_PROVIDER_USED, LAST_PROVIDER_FALLBACKS, LAST_PROVIDER_ERROR

    primary = LLM_PROVIDER if LLM_PROVIDER in PROVIDERS else "ollama"
    order = [primary] + [p for p in LLM_FALLBACKS if p != primary and p in PROVIDERS]
    attempted: List[str] = []
    errors: List[str] = []

    for provider in order:
        if not _provider_configured(provider):
            errors.append(f"{provider}: not configured")
            continue
        attempted.append(provider)
        try:
            result = _call_provider(provider, messages, max_tokens, temperature)
            LAST_PROVIDER_USED = provider
            LAST_PROVIDER_FALLBACKS = attempted[:-1]
            LAST_PROVIDER_ERROR = ""
            return result
        except Exception as exc:
            errors.append(f"{provider}: {str(exc)[:180]}")

    LAST_PROVIDER_USED = attempted[-1] if attempted else primary
    LAST_PROVIDER_FALLBACKS = attempted[:-1]
    LAST_PROVIDER_ERROR = " | ".join(errors)
    raise RuntimeError("All configured LLM providers failed. " + LAST_PROVIDER_ERROR)


def check_providers_health() -> Dict:
    """Return health/configuration information for every supported LLM provider."""
    results = {}
    for provider, cfg in PROVIDERS.items():
        configured = _provider_configured(provider)
        started = time.monotonic()
        try:
            if cfg["kind"] == "local":
                response = requests.get(f"{cfg['base_url']}/api/tags", timeout=3)
                response.raise_for_status()
            else:
                if not configured:
                    raise RuntimeError(f"Missing {cfg['api_key_env']}")
                response = requests.get(
                    f"{cfg['base_url']}/models",
                    headers=_provider_headers(provider),
                    timeout=8,
                )
                response.raise_for_status()
            results[provider] = {
                "name": cfg["name"],
                "configured": configured,
                "healthy": True,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "model": cfg["model"],
                "error": "",
            }
        except Exception as exc:
            results[provider] = {
                "name": cfg["name"],
                "configured": configured,
                "healthy": False,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "model": cfg["model"],
                "error": str(exc)[:220],
            }
    return {
        "active": LLM_PROVIDER,
        "last_used": LAST_PROVIDER_USED,
        "last_fallbacks": LAST_PROVIDER_FALLBACKS,
        "providers": results,
    }


def test_provider(provider: str) -> Dict:
    """Run a small explicit completion test for one provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    started = time.monotonic()
    try:
        text = _call_provider(
            provider,
            [{"role": "user", "content": "Reply with exactly: PROVIDER_OK"}],
            max_tokens=8,
            temperature=0,
        )
        return {
            "provider": provider,
            "success": True,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "response": text[:100],
            "error": "",
        }
    except Exception as exc:
        return {
            "provider": provider,
            "success": False,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "response": "",
            "error": str(exc)[:300],
        }


def set_active_provider(provider: str) -> Dict:
    """Persist and activate the requested provider."""
    global LLM_PROVIDER, LAST_PROVIDER_USED, LAST_PROVIDER_ERROR
    provider = (provider or "").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    if not _provider_configured(provider):
        cfg = PROVIDERS[provider]
        raise ValueError(f"{cfg['name']} is not configured. Set {cfg['api_key_env']} first.")

    LLM_PROVIDER = provider
    LAST_PROVIDER_USED = provider
    LAST_PROVIDER_ERROR = ""
    _write_env_key("LLM_PROVIDER", provider)
    return {
        "active_provider": provider,
        "provider": PROVIDERS[provider],
        "fallbacks": LLM_FALLBACKS,
    }


def set_fallback_chain(chain: List[str]) -> Dict:
    """Persist an ordered fallback chain, excluding the active provider."""
    global LLM_FALLBACKS
    cleaned = []
    for provider in chain:
        name = str(provider).strip().lower()
        if name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {name}")
        if name == LLM_PROVIDER or name in cleaned:
            continue
        cleaned.append(name)
    LLM_FALLBACKS = cleaned
    _write_env_key("LLM_FALLBACKS", ",".join(LLM_FALLBACKS))
    return {"active_provider": LLM_PROVIDER, "fallbacks": LLM_FALLBACKS}


def _find_env_path() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in [here.parent / ".env", here / ".env", Path(".env")]:
        if candidate.exists():
            return candidate
    return here.parent / ".env"


def _write_env_key(key: str, value: str) -> None:
    env_path = _find_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    raw = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = raw.splitlines() if raw else []
    prefix = f"{key}="
    for index, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[index] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")




# ─────────────────────────────────────────────────────────────────────────────
# Agent Definitions
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent


AGENTS = {
    "triage": {
        "name": "Router",
        "emoji": "🔀",
        "system": """You are a router. Analyze the user's request and output ONLY JSON:
{"agent": "<agent_name>", "reason": "<one sentence>"}

Routes:
- "search" → user wants current info, news, facts, research
- "code" → user wants to write/run/debug code
- "image" → user wants to generate/create images
- "general" → everything else: reasoning, analysis, writing, advice""",
    },

    "search": {
        "name": "Web Search",
        "emoji": "🌐",
        "system": """You are a web search agent. Use tools when current or externally verifiable information is needed.
Available tool call JSON: {\"tool\":\"search_web\",\"args\":{\"query\":\"...\"}}
After receiving TOOL_RESULT, synthesize a concise answer and include source URLs from the results when relevant.
Do not invent sources.""",
    },

    "code": {
        "name": "Code Agent",
        "emoji": "💻",
        "system": """You are a Python expert. You may execute user-requested Python with the restricted execution tool.
Tool call JSON: {\"tool\":\"execute_python_code\",\"args\":{\"code\":\"...\"}}
Only execute code when the user explicitly asks to run/execute/test it. Otherwise explain or write the code.
Always explain the result and handle errors clearly.""",
    },

    "image": {
        "name": "Image Generator",
        "emoji": "🎨",
        "system": """You are an image generation expert.
Tool call JSON: {\"tool\":\"generate_image\",\"args\":{\"prompt\":\"...\",\"engine\":\"pollinations\"}}
Use the tool when the user asks to create/generate an image. Then report the generated output path or the exact failure.""",
    },

    "general": {
        "name": "General Assistant",
        "emoji": "🤖",
        "system": """You are a helpful, intelligent assistant.
You may call tools using one JSON object per response when needed:
{\"tool\":\"search_web|execute_python_code|generate_image\",\"args\":{...}}
Use tools only when they materially help answer the request. After a TOOL_RESULT, provide the final answer.""",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Routing Logic
# ─────────────────────────────────────────────────────────────────────────────

def route_request(user_message: str) -> str:
    """Determine which agent should handle this request."""
    messages = [
        {
            "role": "system",
            "content": AGENTS["triage"]["system"],
        },
        {
            "role": "user",
            "content": f"Route this request: {user_message}",
        },
    ]

    resp = _llm(messages, max_tokens=100, temperature=0.3)

    try:
        data = json.loads(resp)
        agent = data.get("agent", "general")
        if agent not in AGENTS:
            agent = "general"
        return agent
    except json.JSONDecodeError:
        return "general"


# ─────────────────────────────────────────────────────────────────────────────
# Tool wrapper functions (for agents to call)
# ─────────────────────────────────────────────────────────────────────────────

def search_tool(query: str) -> str:
    """Wrapper for web search."""
    return tools.format_search_results(query, tools.web_search(query, max_results=5))


def code_tool(code: str) -> str:
    """Wrapper for code execution."""
    result = tools.execute_code(code, language="python", timeout=10)
    if result["success"]:
        return f"✅ Output:\n{result['stdout']}"
    else:
        return f"❌ Error:\n{result['stderr']}"


def image_tool(prompt: str, engine: str = "pollinations") -> str:
    """Wrapper for image generation."""
    img, error = tools.ImageGenerator.generate(prompt, engine=engine)
    
    if error:
        return f"❌ Failed: {error}"
    
    if img:
        filename = tools.save_image(img, output_dir=str(PROJECT_ROOT / "outputs"))
        return f"✅ Generated: /outputs/{filename}"
    
    return "❌ No image returned"


def _parse_tool_call(text: str) -> Optional[Tuple[str, Dict]]:
    """Extract the first valid JSON tool-call object from model output."""
    decoder = json.JSONDecoder()
    for index, char in enumerate(text or ""):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get("tool"), str):
            continue
        tool_name = obj["tool"].strip()
        args = obj.get("args") or {}
        if tool_name in {"search_web", "execute_python_code", "generate_image"} and isinstance(args, dict):
            return tool_name, args
    return None


def _execute_tool(tool_name: str, args: Dict) -> str:
    if tool_name == "search_web":
        query = str(args.get("query", "")).strip()
        if not query:
            return "Tool error: query is required"
        return search_tool(query)
    if tool_name == "execute_python_code":
        return code_tool(str(args.get("code", "")))
    if tool_name == "generate_image":
        prompt = str(args.get("prompt", "")).strip()
        engine = str(args.get("engine", "pollinations"))
        if not prompt:
            return "Tool error: prompt is required"
        return image_tool(prompt, engine=engine)
    return f"Tool error: unsupported tool {tool_name}"


# ─────────────────────────────────────────────────────────────────────────────
# Main Agent Loop
# ─────────────────────────────────────────────────────────────────────────────

def process_message(
    user_message: str,
    session_id: str,
    agent_override: Optional[str] = None,
) -> Dict:
    """Process a message through routing, optional tool execution, and final response."""
    agent_name = agent_override or route_request(user_message)
    agent_def = AGENTS.get(agent_name, AGENTS["general"])
    history = mem.get_history(session_id, limit=10)
    messages = [{"role": "system", "content": agent_def["system"]}]

    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    tools_used: List[str] = []
    response = ""
    max_iterations = 4

    try:
        for _ in range(max_iterations):
            response = _llm(messages, max_tokens=2000, temperature=0.7)
            tool_call = _parse_tool_call(response)
            if not tool_call:
                break
            tool_name, args = tool_call
            tool_result = _execute_tool(tool_name, args)
            tools_used.append(tool_name)
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"TOOL_RESULT ({tool_name}):\n{tool_result}"})
        else:
            response = "Tool execution limit reached. Please narrow the request."
    except Exception as exc:
        response = f"❌ Error: {str(exc)[:500]}"

    mem.save_message(session_id, "user", user_message, agent_name)
    mem.save_message(session_id, "assistant", response, agent_name)

    return {
        "response": response,
        "agent": agent_name,
        "agent_emoji": agent_def["emoji"],
        "tools_used": tools_used,
    }

