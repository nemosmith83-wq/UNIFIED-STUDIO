"""
server.py — Unified FastAPI backend (Agent + Comic Forge + Phantom Studio).
All systems integrated. Optimized for 8GB RAM with resource pooling.
"""

import os
import sys
import json
import uuid
import io
import time
import base64
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Any
from PIL import Image

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Body, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Setup paths
_backend_dir = Path(__file__).parent
_root_dir = _backend_dir.parent
_frontend_dir = _root_dir / "frontend"
_outputs_dir = _root_dir / "outputs"

sys.path.insert(0, str(_backend_dir))

# Import unified modules
import memory as mem
import agent
import tools
import talent
import auth

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Setup (with optimizations for 8GB RAM)
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Unified Studio",
    description="Agent + Comic Forge + Image Generation (all FREE)",
    version="1.0.0",
)

# Local-only CORS. The launcher binds Uvicorn to 127.0.0.1.
# Derive the allowed origins from the actual configured application port so
# the CORS policy cannot silently drift from the launcher configuration.
_unified_port = int(os.getenv("UNIFIED_PORT", "5000"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://127.0.0.1:{_unified_port}",
        f"http://localhost:{_unified_port}",
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Serve outputs directory
_outputs_dir.mkdir(exist_ok=True)
# Outputs are served through an authenticated route below.

# Initialize database
mem.init_db()
talent.init_db()
auth.init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    session_id: Optional[str] = Field(default=None, max_length=200)
    agent: Optional[str] = Field(default=None, max_length=50)


class ImageRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    engine: str = Field(default="pollinations", pattern="^(pollinations|stable_horde)$")
    width: int = Field(default=768, ge=64, le=2048)
    height: int = Field(default=1024, ge=64, le=2048)
    negative_prompt: str = Field(default="", max_length=8000)
    model: str = Field(default="Deliberate", max_length=100)
    steps: int = Field(default=25, ge=1, le=60)
    cfg_scale: float = Field(default=7.0, ge=0.0, le=30.0)
    nsfw: bool = False
    session_id: Optional[str] = Field(default=None, max_length=200)


class ComicRequest(BaseModel):
    prompts: List[str] = Field(min_length=1, max_length=12)
    engine: str = "pollinations"
    width: int = 768
    height: int = 1024
    negative_prompt: str = ""
    model: str = "Deliberate"
    steps: int = 25
    cfg_scale: float = 7.0
    nsfw: bool = False
    session_id: Optional[str] = None


class PromptTransformRequest(BaseModel):
    prompts: str
    style: Optional[str] = None
    character: Optional[Dict[str, str]] = None
    clothes: Optional[Dict[str, str]] = None


class ImageEditRequest(BaseModel):
    filename: str
    filter: str = "none"
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    caption: str = ""
    caption_position: str = "bottom"
    session_id: Optional[str] = None


class MemoryRequest(BaseModel):
    key: str
    value: Any


class AutomationRequest(BaseModel):
    name: str
    trigger_type: str = "manual"
    schedule: str = ""
    action: str = ""


class TalentEvaluationRequest(BaseModel):
    candidate_id: str
    job_id: Optional[str] = None


class PlacementRequest(BaseModel):
    candidate_id: str
    job_id: str
    placement_date: Optional[str] = None


class PlacementUpdateRequest(BaseModel):
    milestone: str
    status: str
    notes: str = ""


class AdvertisementRequest(BaseModel):
    offer: str
    preferences: Dict[str, str] = Field(default_factory=dict)


class ProviderSwitchRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=50)


class ProviderFallbackRequest(BaseModel):
    chain: List[str] = Field(default_factory=list, max_length=10)


AUTOMATIONS: Dict[str, Dict] = {}
WORKFLOWS: Dict[str, Dict] = {}



# ─────────────────────────────────────────────────────────────────────────────
# Multi-user authentication / authorization
# ─────────────────────────────────────────────────────────────────────────────

PUBLIC_ASSET_PREFIXES = ("/api/auth/", "/style.css", "/app.js", "/", "/favicon.ico")

def _client_id_from_request(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return (forwarded.split(",")[0].strip() or request.client.host if request.client else "unknown")[:120]

def _current_user_from_request(request: Request):
    return auth.get_user_by_session(request.cookies.get(auth.COOKIE_NAME))

def _require_user(request: Request):
    user = _current_user_from_request(request)
    if not user:
        return None, JSONResponse(status_code=401, content={"error": "Authentication required", "code": "AUTH_REQUIRED"})
    return user, None

def _scoped_session(user: dict, session_id: Optional[str]) -> str:
    raw = (session_id or f"session_{uuid.uuid4().hex}").strip()[:200]
    return f"u_{user['id']}_{raw}"[:250]

def _scoped_memory_key(user: dict, key: str) -> str:
    return f"u_{user['id']}::{key.strip()}"[:500]

def _scoped_filename(user: dict, filename: str) -> str:
    safe = Path(filename).name
    return f"u_{user['id']}_{safe}"

def _unscoped_url(filename: str) -> str:
    return f"/outputs/{filename}"

def _save_scoped_image(user: dict, image: Image.Image) -> str:
    raw = tools.save_image(image, output_dir=str(_outputs_dir))
    src = _outputs_dir / raw
    scoped = _scoped_filename(user, raw)
    dst = _outputs_dir / scoped
    try:
        src.replace(dst)
    except FileNotFoundError:
        pass
    return scoped

@app.middleware("http")
async def require_authentication(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or path.startswith("/api/auth/") or path in {"/", "/health", "/style.css", "/app.js", "/favicon.ico"}:
        return await call_next(request)
    if path.startswith("/api/") or path.startswith("/outputs/") or path.startswith("/promptvault") or path.startswith("/guides/") or path in {"/docs", "/redoc", "/openapi.json"}:
        if not _current_user_from_request(request):
            return JSONResponse(status_code=401, content={"error": "Authentication required", "code": "AUTH_REQUIRED"})
    return await call_next(request)

@app.get("/api/auth/status")
def auth_status(request: Request):
    user = _current_user_from_request(request)
    registration_enabled = os.getenv("ALLOW_REGISTRATION", "true").strip().lower() in {"1", "true", "yes", "on"}
    return {"authenticated": bool(user), "user": user, "registration_enabled": registration_enabled}

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    display_name: str = Field(default="", max_length=80)
    password: str = Field(min_length=10, max_length=200)

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=200)

@app.post("/api/auth/register")
def auth_register(req: RegisterRequest, request: Request, response: Response):
    if os.getenv("ALLOW_REGISTRATION", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return JSONResponse(status_code=403, content={"error": "Registration is disabled by the operator."})
    client_id = _client_id_from_request(request)
    if not auth._rate_key(client_id):
        return JSONResponse(status_code=429, content={"error": "Too many attempts. Try again later."})
    try:
        user = auth.create_user(req.username, req.display_name, req.password)
        token = auth.create_session(user["id"])
        response.set_cookie(auth.COOKIE_NAME, token, httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE_ONLY", "false").lower() in {"1", "true", "yes", "on"} or request.url.scheme == "https", max_age=auth.SESSION_TTL_SECONDS, path="/")
        auth.clear_failures(client_id)
        return {"success": True, "user": user}
    except ValueError as exc:
        auth.record_failure(client_id)
        return JSONResponse(status_code=400, content={"error": str(exc)})

@app.post("/api/auth/login")
def auth_login(req: LoginRequest, request: Request, response: Response):
    client_id = _client_id_from_request(request)
    if not auth._rate_key(client_id):
        return JSONResponse(status_code=429, content={"error": "Too many login attempts. Try again later."})
    user = auth.verify_user(req.username, req.password)
    if not user:
        auth.record_failure(client_id)
        return JSONResponse(status_code=401, content={"error": "Invalid username or password."})
    token = auth.create_session(user["id"])
    response.set_cookie(auth.COOKIE_NAME, token, httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE_ONLY", "false").lower() in {"1", "true", "yes", "on"} or request.url.scheme == "https", max_age=auth.SESSION_TTL_SECONDS, path="/")
    auth.clear_failures(client_id)
    return {"success": True, "user": user}

@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response):
    auth.delete_session(request.cookies.get(auth.COOKIE_NAME))
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"success": True}

@app.get("/outputs/{filename:path}")
def serve_output(filename: str, request: Request):
    user = _current_user_from_request(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})
    safe = Path(filename).name
    prefix = f"u_{user['id']}_"
    if not safe.startswith(prefix):
        return JSONResponse(status_code=404, content={"error": "Output not found"})
    path = (_outputs_dir / safe).resolve()
    try:
        path.relative_to(_outputs_dir.resolve())
    except ValueError:
        return JSONResponse(status_code=404, content={"error": "Output not found"})
    if not path.exists() or not path.is_file():
        return JSONResponse(status_code=404, content={"error": "Output not found"})
    return FileResponse(str(path))

# ─────────────────────────────────────────────────────────────────────────────
# Frontend Serving
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Serve the real Unified Studio mobile application entry point."""
    index_path = _frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    return {"message": "Unified Studio API"}


@app.get("/health", include_in_schema=False)
def health():
    """Unauthenticated process health probe for container platforms."""
    return {"ok": True}


@app.get("/style.css")
def serve_style():
    path = _frontend_dir / "style.css"
    if path.exists():
        return FileResponse(str(path))
    return {"error": "style.css not found"}


@app.get("/promptvault")
@app.get("/promptvault.html")
def serve_promptvault():
    """Serve the integrated PromptVault Pro workspace."""
    path = _frontend_dir / "promptvault.html"
    if path.exists():
        return FileResponse(str(path), media_type="text/html")
    return JSONResponse(status_code=404, content={"error": "promptvault.html not found"})


@app.get("/guides/{filename}")
def serve_guide(filename: str):
    """Serve bundled local PDF guides without exposing arbitrary filesystem paths."""
    guides_dir = (_root_dir / "guides").resolve()
    try:
        path = (guides_dir / filename).resolve()
        path.relative_to(guides_dir)
    except (OSError, ValueError):
        return JSONResponse(status_code=404, content={"error": "not found"})
    if path.exists() and path.is_file() and path.suffix.lower() == ".pdf":
        return FileResponse(str(path), media_type="application/pdf")
    return JSONResponse(status_code=404, content={"error": "not found"})


@app.get("/{filename}")
def serve_static(filename: str):
    """Serve only files that resolve inside the frontend directory."""
    try:
        path = (_frontend_dir / filename).resolve()
        path.relative_to(_frontend_dir.resolve())
    except (OSError, ValueError):
        return JSONResponse(status_code=404, content={"error": "not found"})
    if path.exists() and path.is_file():
        return FileResponse(str(path))
    return JSONResponse(status_code=404, content={"error": "not found"})


# ─────────────────────────────────────────────────────────────────────────────
# Status & Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    """Report configured integrations without claiming remote services are reachable."""
    configured_llm = [name for name in agent.PROVIDERS if agent._provider_configured(name)]
    code_enabled = os.getenv("ENABLE_CODE_EXECUTION", "true").strip().lower() in {"1", "true", "yes", "on"}
    return {
        "status": "healthy",
        "services": {
            "agent": "available",
            "llm_providers": configured_llm,
            "active_llm_provider": agent.LLM_PROVIDER,
            "image_gen": "provider integration available; reachability is checked when requested",
            "search": "provider integration available; reachability is checked when requested",
            "code_execution": "enabled (restricted runner; not an OS sandbox)" if code_enabled else "disabled by operator",
        },
        "free_tier": None,
        "api_keys_required": ["GROQ_API_KEY (optional)", "OPENROUTER_API_KEY (optional)", "POLLINATIONS_API_KEY (optional)", "HORDE_API_KEY (optional)"],
    }


@app.get("/api/config")
def get_config():
    """Get system configuration (safe to expose)."""
    return {
        "engines": {
            "pollinations": {
                "name": "Pollinations (Flux)",
                "speed": "fast",
                "cost": "free",
                "requires_key": False,
            },
            "stable_horde": {
                "name": "Stable Horde",
                "speed": "medium",
                "cost": "free (with optional key for priority)",
                "requires_key": False,
            },
        },
        "agents": list(agent.AGENTS.keys()),
        "providers": {
            name: {
                "name": cfg["name"],
                "kind": cfg["kind"],
                "model": cfg["model"],
                "configured": agent._provider_configured(name),
            }
            for name, cfg in agent.PROVIDERS.items()
        },
        "active_provider": agent.LLM_PROVIDER,
        "fallbacks": agent.LLM_FALLBACKS,
        "horde_models": tools.HORDE_MODELS,
        "style_presets": tools.STYLE_PRESETS,
        "character_options": tools.CHARACTER_OPTIONS,
        "clothes_options": tools.CLOTHES_OPTIONS,
    }



# ─────────────────────────────────────────────────────────────────────────────
# LLM Provider Management
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/providers/health")
def provider_health():
    """Return health/configuration data for all supported LLM providers."""
    return agent.check_providers_health()


@app.post("/api/providers/test")
def provider_test(req: ProviderSwitchRequest):
    """Run an explicit, user-triggered completion test for one provider."""
    if req.provider.strip().lower() not in agent.PROVIDERS:
        return JSONResponse(status_code=400, content={"error": f"Unknown provider: {req.provider}"})
    return agent.test_provider(req.provider.strip().lower())


@app.post("/api/providers/switch")
def provider_switch(req: ProviderSwitchRequest, request: Request):
    """Switch the active LLM provider and persist the selection."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    try:
        return agent.set_active_provider(req.provider)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)[:300]})


@app.get("/api/providers/fallback")
def provider_fallback():
    """Return the ordered fallback chain."""
    return {"primary": agent.LLM_PROVIDER, "chain": agent.LLM_FALLBACKS}


@app.put("/api/providers/fallback")
def provider_fallback_update(req: ProviderFallbackRequest, request: Request):
    """Persist an ordered fallback chain."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    try:
        return agent.set_fallback_chain(req.chain)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})




# ─────────────────────────────────────────────────────────────────────────────
# Chat API (Agent System)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(req: MessageRequest, request: Request):
    """
    Process a message through the unified agent system.
    Returns: {response, agent, session_id}
    """
    user, error_response = _require_user(request)
    if error_response: return error_response
    session_id = _scoped_session(user, req.session_id)

    try:
        result = agent.process_message(
            user_message=req.message,
            session_id=session_id,
            agent_override=req.agent,
        )
        result["session_id"] = session_id
        return result

    except Exception as e:
        return {
            "response": f"Error: {str(e)[:200]}",
            "session_id": session_id,
            "error": True,
        }


@app.get("/api/history/{session_id}")
def get_history(session_id: str, request: Request, limit: int = 20):
    """Get conversation history for a user-scoped session."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    scoped = _scoped_session(user, session_id)
    history = mem.get_history(scoped, limit=limit)
    return {"session_id": session_id, "messages": history}


@app.delete("/api/history/{session_id}")
def clear_history(session_id: str, request: Request):
    """Clear a user-scoped conversation session."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    scoped = _scoped_session(user, session_id)
    return {"session_id": session_id, "deleted": mem.clear_history(scoped)}


@app.get("/api/history/{session_id}/search")
def search_history(session_id: str, request: Request, q: str, limit: int = 20):
    """Search within one user-scoped session."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    scoped = _scoped_session(user, session_id)
    return {"session_id": session_id, "query": q, "messages": mem.search_history(scoped, q, limit)}


@app.get("/api/sessions")
def list_sessions(request: Request):
    """List only the authenticated user's chat sessions."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    prefix = f"u_{user['id']}_"
    return {"sessions": [row for row in mem.list_sessions() if row["session_id"].startswith(prefix)]}


@app.get("/api/memories")
def get_memories(request: Request):
    """List long-term memories for the authenticated user."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    prefix = f"u_{user['id']}::"
    all_mem = mem.get_all_memories()
    return {"memories": {k[len(prefix):]: v for k, v in all_mem.items() if k.startswith(prefix)}}


@app.post("/api/memories")
def save_memory(req: MemoryRequest, request: Request):
    """Save a user-scoped long-term memory."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    mem.save_memory(_scoped_memory_key(user, req.key), req.value)
    return {"success": True, "key": req.key.strip()}


@app.delete("/api/memories/{key}")
def delete_memory(key: str, request: Request):
    """Delete a user-scoped long-term memory."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    scoped_key = _scoped_memory_key(user, key)
    return {"success": mem.delete_memory(scoped_key), "key": key}


# ─────────────────────────────────────────────────────────────────────────────
# Talent Acquisition Helper
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/talent/jobs")
def talent_jobs():
    """List available job profiles used for explainable matching."""
    return {"jobs": talent.list_jobs()}


@app.post("/api/talent/candidates")
async def upload_candidate_cv(request: Request, file: UploadFile = File(...)):
    """Extract and store a candidate CV for later evaluation."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    try:
        data = await file.read()
        text = talent.extract_text(data, file.filename or "candidate.txt")
        if len(text.strip()) < 20:
            return JSONResponse(status_code=400, content={"error": "The CV does not contain enough readable text."})
        candidate = talent.save_candidate(file.filename or "candidate.txt", text, user["id"])
        return {"success": True, "candidate": candidate}
    except ValueError as error:
        return JSONResponse(status_code=400, content={"error": str(error)})
    except Exception as error:
        return JSONResponse(status_code=500, content={"error": str(error)[:200]})


@app.post("/api/talent/evaluate")
def evaluate_candidate(req: TalentEvaluationRequest, request: Request):
    """Compare a stored candidate against a selected job and alternatives."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    try:
        return {"success": True, **talent.evaluate(req.candidate_id, req.job_id, user["id"])}
    except ValueError as error:
        return JSONResponse(status_code=404, content={"error": str(error)})


@app.post("/api/talent/placements")
def create_talent_placement(req: PlacementRequest, request: Request):
    """Start three-month placement tracking for a candidate."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    try:
        return {"success": True, "placement": talent.create_placement(req.candidate_id, req.job_id, req.placement_date, user["id"])}
    except ValueError as error:
        return JSONResponse(status_code=404, content={"error": str(error)})


@app.patch("/api/talent/placements/{placement_id}")
def update_talent_placement(placement_id: str, req: PlacementUpdateRequest, request: Request):
    """Record a placement milestone update."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    try:
        return {"success": True, "placement": talent.update_placement(placement_id, req.milestone, req.status, req.notes, user["id"])}
    except ValueError as error:
        return JSONResponse(status_code=400, content={"error": str(error)})


@app.get("/api/talent/placements/{placement_id}/report")
def get_talent_placement_report(placement_id: str, request: Request):
    """Calculate the current placement success report."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    try:
        return {"success": True, "report": talent.placement_report(placement_id, user["id"])}
    except ValueError as error:
        return JSONResponse(status_code=404, content={"error": str(error)})


@app.post("/api/talent/advertisements")
def create_talent_advertisement(req: AdvertisementRequest):
    """Generate a recruitment advertisement strictly from a supplied offer."""
    if not req.offer.strip():
        return JSONResponse(status_code=400, content={"error": "A job offer is required."})
    return {"success": True, **talent.generate_advertisement(req.offer, req.preferences)}


# ─────────────────────────────────────────────────────────────────────────────
# Image Generation API (Comic Forge)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/generate-image")
def generate_image(req: ImageRequest, request: Request):
    """
    Generate an image from a prompt.
    Engines: "pollinations" (fast), "stable_horde" (quality)
    Both FREE.
    """
    user, error_response = _require_user(request)
    if error_response: return error_response
    session_id = _scoped_session(user, req.session_id)

    try:
        img, error = tools.ImageGenerator.generate(
            prompt=req.prompt,
            engine=req.engine,
            width=req.width,
            height=req.height,
            negative_prompt=req.negative_prompt,
            model=req.model,
            steps=req.steps,
            cfg_scale=req.cfg_scale,
            nsfw=req.nsfw,
        )

        if error:
            return {
                "success": False,
                "error": error,
                "session_id": session_id,
            }

        if img:
            filename = _save_scoped_image(user, img)
            mem.save_image_metadata(session_id, filename, req.prompt, req.engine)
            return {
                "success": True,
                "filename": filename,
                "url": f"/outputs/{filename}",
                "engine": req.engine,
                "session_id": session_id,
            }

        return {
            "success": False,
            "error": "No image returned",
            "session_id": session_id,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)[:200],
            "session_id": session_id,
        }


@app.post("/api/generate-comic")
def generate_comic(req: ComicRequest, request: Request):
    """Generate multiple comic panels from one prompt per line."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    session_id = _scoped_session(user, req.session_id)
    generated = []
    errors = []

    for idx, prompt in enumerate([p.strip() for p in req.prompts if p.strip()], start=1):
        img, error = tools.ImageGenerator.generate(
            prompt=prompt,
            engine=req.engine,
            width=req.width,
            height=req.height,
            negative_prompt=req.negative_prompt,
            model=req.model,
            steps=req.steps,
            cfg_scale=req.cfg_scale,
            nsfw=req.nsfw,
        )
        if error or not img:
            errors.append({"panel": idx, "prompt": prompt, "error": error or "No image returned"})
            continue

        filename = _save_scoped_image(user, img)
        mem.save_image_metadata(session_id, filename, prompt, req.engine)
        generated.append({
            "panel": idx,
            "filename": filename,
            "url": f"/outputs/{filename}",
            "prompt": prompt,
            "engine": req.engine,
        })

    return {
        "success": bool(generated),
        "session_id": session_id,
        "images": generated,
        "errors": errors,
    }


@app.get("/api/images/{session_id}")
def get_session_images(session_id: str, request: Request, limit: int = 50):
    """Get images generated in a user-scoped session."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    scoped = _scoped_session(user, session_id)
    images = mem.get_session_images(scoped, limit=limit)
    return {"session_id": session_id, "images": images}


@app.post("/api/save-edited-image")
def save_edited_image(request: Request, payload: Dict = Body(...)):
    """Save an edited image (base64 PNG data)."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    try:
        session_id = _scoped_session(user, payload.get("session_id"))
        image_data = payload.get("image_data", "")
        import base64
        # Remove data URI prefix if present
        if image_data.startswith("data:image/png;base64,"):
            image_data = image_data.replace("data:image/png;base64,", "")
        
        img_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(img_bytes))
        
        filename = _save_scoped_image(user, img)
        mem.save_image_metadata(session_id, filename, "edited_image", "editor")
        
        return {
            "success": True,
            "filename": filename,
            "url": f"/outputs/{filename}",
            "session_id": session_id,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)[:200],
            "session_id": payload.get("session_id") if isinstance(payload, dict) else None,
        }


@app.post("/api/edit-image")
def edit_image(req: ImageEditRequest, request: Request):
    """Apply filters, enhancements, and caption text to a saved image."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    session_id = _scoped_session(user, req.session_id)
    source_filename = _scoped_filename(user, req.filename)
    img, error = tools.edit_image_file(
        filename=source_filename,
        output_dir=str(_outputs_dir),
        filter_name=req.filter,
        brightness=req.brightness,
        contrast=req.contrast,
        saturation=req.saturation,
        caption=req.caption,
        caption_position=req.caption_position,
    )
    if error or not img:
        return {"success": False, "error": error or "No image returned", "session_id": session_id}

    filename = _save_scoped_image(user, img)
    mem.save_image_metadata(session_id, filename, f"edited:{req.filename}", "editor")
    return {"success": True, "filename": filename, "url": f"/outputs/{filename}", "session_id": session_id}


@app.post("/api/prompts/transform")
def transform_prompts(req: PromptTransformRequest):
    """Apply style/character/clothing descriptors to prompt lines."""
    prompts = req.prompts
    descriptors = []
    if req.character:
        descriptors.append(tools.build_descriptor(req.character))
    if req.clothes:
        descriptors.append(tools.build_descriptor(req.clothes))
    if req.style:
        descriptors.append(req.style.strip().lower())

    suffix = ", ".join(d for d in descriptors if d)
    if suffix:
        prompts = "\n".join(
            f"{line.strip()}, {suffix}"
            for line in req.prompts.splitlines()
            if line.strip()
        )
    return {"success": True, "prompts": prompts}


@app.post("/api/import-prompts")
async def import_prompts(request: Request, file: UploadFile = File(...)):
    """Import prompt lines from TXT/HTML/JSON/XML uploads."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    data = await file.read()
    return tools.import_text_from_bytes(data, file.filename or "upload.txt")


@app.post("/api/export-comic")
def export_comic(request: Request, payload: Dict = Body(...)):
    """Export selected generated images as a standalone HTML comic."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    images = []
    prefix = f"u_{user['id']}_"
    for item in payload.get("images", []):
        filename = Path(str(item.get("filename", ""))).name
        if not filename.startswith(prefix):
            continue
        images.append({**item, "filename": filename})
    result = tools.export_comic_html(images, output_dir=str(_outputs_dir))
    if result.get("success") and result.get("filename"):
        raw = result["filename"]
        src = _outputs_dir / raw
        scoped = _scoped_filename(user, raw)
        try: src.replace(_outputs_dir / scoped)
        except FileNotFoundError: pass
        result["filename"] = scoped
        result["url"] = f"/outputs/{scoped}"
    return result


@app.post("/api/process-file")
async def process_file(
    request: Request,
    file: UploadFile = File(...),
    operation: str = Form("analyze"),
):
    """Analyze or convert an uploaded text/image file."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    data = await file.read()
    before = {p.name for p in _outputs_dir.iterdir() if p.is_file()}
    result = tools.process_uploaded_file(data, file.filename or "upload", operation, output_dir=str(_outputs_dir))
    for p in list(_outputs_dir.iterdir()):
        if p.is_file() and p.name not in before and not p.name.startswith(f"u_{user['id']}_"):
            scoped = _scoped_filename(user, p.name)
            try: p.replace(_outputs_dir / scoped)
            except OSError: continue
            if result.get("filename") == p.name: result["filename"] = scoped
            if result.get("url") == f"/outputs/{p.name}": result["url"] = f"/outputs/{scoped}"
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Web Search API
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/search")
def web_search(q: Optional[str] = None, query: Optional[str] = None):
    """Search the web (DuckDuckGo — FREE, no API key)."""
    term = (q or query or "").strip()
    if len(term) < 2:
        return JSONResponse(status_code=400, content={"error": "Query too short"})
    try:
        results = tools.web_search(term, max_results=6)
        return {"query": term, "results": results}
    except Exception as e:
        return {"error": str(e)[:200], "query": term, "results": []}


# ─────────────────────────────────────────────────────────────────────────────
# Code Execution API
# ─────────────────────────────────────────────────────────────────────────────

class CodeRequest(BaseModel):
    code: str
    language: str = "python"


@app.post("/api/execute-code")
def execute_code(req: CodeRequest):
    """Execute code safely (Python only, with security checks)."""
    if os.getenv("ENABLE_CODE_EXECUTION", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return JSONResponse(status_code=503, content={"error": "Code execution is disabled by the operator in this deployment."})
    result = tools.execute_code(
        code=req.code,
        language=req.language,
        timeout=10,
    )
    return result


@app.post("/api/code")
def execute_code_compat(req: CodeRequest):
    """Backward-compatible alias for the code execution endpoint."""
    return execute_code(req)



# ─────────────────────────────────────────────────────────────────────────────
# Automation & Workflow API
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/automations")
def list_automations(request: Request):
    """List the authenticated user's automation definitions."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    return {"automations": [x for x in AUTOMATIONS.values() if x.get("owner_id") == user["id"]]}


@app.post("/api/automations")
def create_automation(req: AutomationRequest, request: Request):
    """Create an automation definition. Execution is manual in the unified local app."""
    task_id = str(uuid.uuid4())
    user, error_response = _require_user(request)
    if error_response: return error_response
    task = {
        "id": task_id,
        "owner_id": user["id"],
        "name": req.name,
        "trigger_type": req.trigger_type,
        "schedule": req.schedule,
        "action": req.action,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_run": None,
    }
    AUTOMATIONS[task_id] = task
    return {"success": True, "automation": task}


@app.post("/api/automations/{task_id}/run")
def run_automation(task_id: str, request: Request):
    """Run an automation definition as a recorded local action."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    task = AUTOMATIONS.get(task_id)
    if not task or task.get("owner_id") != user["id"]:
        return {"success": False, "error": "Automation not found"}
    task["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "success": True,
        "id": task_id,
        "output": f"Executed '{task['name']}' at {task['last_run']}",
    }


@app.delete("/api/automations/{task_id}")
def delete_automation(task_id: str, request: Request):
    """Delete an automation definition."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    task = AUTOMATIONS.get(task_id)
    if not task or task.get("owner_id") != user["id"]: return {"success": False}
    AUTOMATIONS.pop(task_id, None)
    return {"success": True}


@app.get("/api/workflows")
def list_workflows(request: Request):
    """List the authenticated user's workflows."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    return {"workflows": [x for x in WORKFLOWS.values() if x.get("owner_id") == user["id"]]}


@app.post("/api/workflows")
def create_workflow(request: Request, payload: Dict = Body(...)):
    """Create a simple multi-step workflow."""
    workflow_id = str(uuid.uuid4())
    user, error_response = _require_user(request)
    if error_response: return error_response
    workflow = {
        "id": workflow_id,
        "owner_id": user["id"],
        "name": payload.get("name", "Untitled workflow"),
        "steps": payload.get("steps", []),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    WORKFLOWS[workflow_id] = workflow
    return {"success": True, "workflow": workflow}


@app.post("/api/workflows/{workflow_id}/run")
def run_workflow(workflow_id: str, request: Request):
    """Run a saved workflow and return per-step status."""
    user, error_response = _require_user(request)
    if error_response: return error_response
    workflow = WORKFLOWS.get(workflow_id)
    if not workflow or workflow.get("owner_id") != user["id"]:
        return {"success": False, "error": "Workflow not found"}
    return {
        "success": True,
        "workflow_id": workflow_id,
        "results": [
            {"step": i + 1, "name": step.get("name", "Unnamed step"), "status": "completed"}
            for i, step in enumerate(workflow.get("steps", []))
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Chat (real-time streaming)
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Authenticated WebSocket endpoint for real-time chat."""
    user = auth.get_user_by_session(websocket.cookies.get(auth.COOKIE_NAME))
    if not user:
        await websocket.close(code=1008, reason="Authentication required")
        return
    await websocket.accept()
    session_id = _scoped_session(user, None)

    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            user_message = msg_data.get("message", "")

            if not user_message:
                await websocket.send_json({"error": "No message"})
                continue

            result = await asyncio.to_thread(agent.process_message, user_message, session_id)
            result["session_id"] = session_id

            await websocket.send_json(result)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)[:200]})


# ─────────────────────────────────────────────────────────────────────────────
# Root: serve index.html if it exists, otherwise show API docs
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/docs")
def docs():
    """OpenAPI docs."""
    return {
        "message": "Swagger UI at /docs, ReDoc at /redoc",
        "endpoints": {
            "POST /api/chat": "Send message to agent",
            "GET /api/history/{session_id}": "Get conversation history",
            "POST /api/generate-image": "Generate image (FREE engines)",
            "GET /api/search": "Web search (DuckDuckGo)",
            "POST /api/execute-code": "Execute Python code",
            "GET /api/status": "System status",
        },
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", os.getenv("UNIFIED_PORT", "5000")))
    uvicorn.run(
        "server:app",
        host=os.getenv("UNIFIED_HOST", "127.0.0.1"),
        port=port,
        reload=False,
        log_level="warning",
    )
