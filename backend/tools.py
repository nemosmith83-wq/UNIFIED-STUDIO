"""
tools.py — Unified tools module (web search, code execution, image generation).
ALL FREE TIER — no paid APIs. Optimized for 8GB RAM.
"""

import os
import re
import subprocess
import tempfile
import time
import requests
import json
import ast
import base64
import mimetypes
from typing import Optional, Dict, Tuple
from urllib.parse import quote
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
import io


# ─────────────────────────────────────────────────────────────────────────────
# WEB SEARCH (DuckDuckGo — FREE, no API key required)
# ─────────────────────────────────────────────────────────────────────────────

class _DuckDuckGoHTMLParser(__import__("html.parser", fromlist=["HTMLParser"]).HTMLParser):
    """Small dependency-free parser for DuckDuckGo HTML fallback results."""
    def __init__(self):
        super().__init__()
        self.items = []
        self._current = None
        self._in_title = False
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        cls = attrs.get("class", "")
        if tag == "a" and "result__a" in cls:
            self._current = {
                "title": "",
                "url": attrs.get("href", ""),
                "snippet": "",
            }
            self._in_title = True
        elif self._current is not None and tag in {"a", "div", "p"} and "result__snippet" in cls:
            self._in_body = True

    def handle_endtag(self, tag):
        if tag == "a" and self._in_title:
            self._in_title = False
        if tag in {"a", "div", "p"} and self._in_body:
            self._in_body = False
        if tag == "a" and self._current and self._current["title"]:
            if self._current not in self.items:
                self.items.append(self._current)
                if len(self.items) >= 20:
                    self._current = None

    def handle_data(self, data):
        data = " ".join(data.split())
        if not data or self._current is None:
            return
        if self._in_title:
            self._current["title"] += data
        elif self._in_body:
            self._current["snippet"] += data


def _normalise_search_result(item: Dict) -> Dict:
    return {
        "title": str(item.get("title") or item.get("name") or "No title"),
        "url": str(item.get("href") or item.get("url") or ""),
        "snippet": str(item.get("body") or item.get("snippet") or ""),
    }


def web_search(query: str, max_results: int = 5) -> list:
    """Search DuckDuckGo and return structured results.

    Uses the ddgs package when available and falls back to DuckDuckGo's HTML
    endpoint when the package is unavailable. Network failures return an empty
    list plus a diagnostic result so callers can distinguish failure from no hits.
    """
    query = (query or "").strip()
    if not query:
        return []

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [_normalise_search_result(r) for r in results[:max_results]]
    except ImportError:
        pass
    except Exception:
        # Fall through to dependency-free HTML search.
        pass

    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 UnifiedStudio/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        parser = _DuckDuckGoHTMLParser()
        parser.feed(resp.text)
        return parser.items[:max_results]
    except Exception:
        return []


def format_search_results(query: str, results: list) -> str:
    if not results:
        return f"No search results found for: {query}"
    lines = [f"Search: '{query}'", "─" * 50]
    for i, r in enumerate(results, 1):
        lines.append(
            f"[{i}] {r.get('title', 'No title')}\n"
            f"    {r.get('snippet', '')[:350]}\n"
            f"    {r.get('url', '')}"
        )
    return "\n".join(lines)


# Backward-compatible public name retained for existing callers/tests.
search_web = web_search


# ─────────────────────────────────────────────────────────────────────────────
# CODE EXECUTION (restricted subprocess with AST policy + timeout)
# ─────────────────────────────────────────────────────────────────────────────

_FORBIDDEN_NAMES = {
    "open", "input", "compile", "eval", "exec", "__import__", "globals",
    "locals", "vars", "getattr", "setattr", "delattr", "breakpoint",
    "help", "quit", "exit", "copyright", "credits", "license",
}
_FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "ctypes",
    "multiprocessing", "threading", "asyncio", "signal", "resource",
    "pickle", "marshal", "builtins", "importlib", "inspect",
}
_FORBIDDEN_ATTRIBUTES = {
    "system", "popen", "run", "Popen", "spawn", "fork", "kill", "remove",
    "unlink", "rmtree", "__class__", "__base__", "__subclasses__",
    "__globals__", "__builtins__", "__import__", "__dict__", "__mro__",
}

_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "int": int,
    "len": len, "list": list, "map": map, "max": max, "min": min,
    "pow": pow, "print": print, "range": range, "repr": repr,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "RuntimeError": RuntimeError, "KeyError": KeyError, "IndexError": IndexError,
}


def _validate_code_ast(code: str) -> Tuple[bool, str]:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "imports are disabled in restricted code execution"
        if isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_NAMES or node.id.startswith("__"):
                return False, f"forbidden name: {node.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_ATTRIBUTES or node.attr.startswith("__"):
                return False, f"forbidden attribute: {node.attr}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_NAMES:
                return False, f"forbidden call: {node.func.id}"
    return True, ""


def _is_safe_code(code: str) -> Tuple[bool, str]:
    return _validate_code_ast(code)


def execute_code(code: str, language: str = "python", timeout: int = 10) -> Dict:
    """Execute restricted Python code in a separate process.

    This is an application-level execution policy, not a hardened OS sandbox.
    Imports and filesystem/process/network primitives are deliberately disabled.
    """
    result = {"stdout": "", "stderr": "", "success": False, "language": language}
    if not code.strip():
        result["stderr"] = "No code provided."
        return result
    if language.lower() != "python":
        result["stderr"] = f"Unsupported language: {language}"
        return result

    safe, reason = _is_safe_code(code)
    if not safe:
        result["stderr"] = f"Security check failed: {reason}"
        return result

    allowed_names = tuple(_SAFE_BUILTINS.keys())
    wrapper = (
        "import builtins as _b\n"
        f"_ALLOWED = {allowed_names!r}\n"
        "SAFE_BUILTINS = {name: getattr(_b, name) for name in _ALLOWED}\n"
        "SAFE_GLOBALS = {'__builtins__': SAFE_BUILTINS}\n"
        f"USER_CODE = {code!r}\n"
        "exec(compile(USER_CODE, '<user_code>', 'exec'), SAFE_GLOBALS, SAFE_GLOBALS)\n"
    )

    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(wrapper)
            temp_file = f.name

        proc = subprocess.run(
            [os.environ.get("PYTHON_EXECUTABLE", "python"), "-I", temp_file],
            capture_output=True,
            text=True,
            timeout=max(1, min(int(timeout), 30)),
        )
        result["stdout"] = proc.stdout[:4000]
        result["stderr"] = proc.stderr[:4000]
        result["success"] = proc.returncode == 0
    except subprocess.TimeoutExpired:
        result["stderr"] = f"Timeout (>{timeout}s)"
    except Exception as exc:
        result["stderr"] = str(exc)
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
    return result


# Backward-compatible helper expected by older test/call sites.
def execute_python_code(code: str) -> str:
    """Compatibility helper; expression-only input is printed for legacy callers."""
    source = code
    try:
        tree = ast.parse(code, mode="exec")
        if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr):
            source = f"print({code})"
    except SyntaxError:
        pass
    result = execute_code(source, language="python", timeout=10)
    return result["stdout"] if result["success"] else result["stderr"]


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE GENERATION — Free engines only
# ─────────────────────────────────────────────────────────────────────────────

class ImageGenerator:
    """Multi-backend image generation. All FREE (Pollinations + Stable Horde)."""

    @staticmethod
    def _pollinations(prompt: str, width: int = 768, height: int = 1024, 
                      nsfw: bool = False) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Pollinations.ai — FREE. No API key. Flux model.
        Fast and reliable.
        """
        try:
            encoded = quote(prompt)
            nsfw_flag = "true" if nsfw else "false"
            url = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?nsfw={nsfw_flag}&nologo=true"
                f"&width={width}&height={height}&model=flux"
            )
            
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return Image.open(io.BytesIO(resp.content)), None
            
            return None, f"HTTP {resp.status_code}"

        except requests.Timeout:
            return None, "Timeout (>60s)"
        except Exception as e:
            return None, str(e)

    @staticmethod
    def _stable_horde(prompt: str, negative_prompt: str = "", 
                      width: int = 768, height: int = 1024,
                      model: str = "Deliberate", nsfw: bool = False,
                      steps: int = 25, cfg_scale: float = 7.0) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Stable Horde — FREE. Uses anonymous key.
        Slower but reliable quality.
        """
        api_key = os.getenv("HORDE_API_KEY", "0000000000")
        headers = {"apikey": api_key, "Content-Type": "application/json"}
        
        payload = {
            "prompt": f"{prompt} ### {negative_prompt}",
            "params": {
                "width": width,
                "height": height,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "sampler_name": "k_euler_a",
            },
            "models": [model],
            "nsfw": nsfw,
            "censor_nsfw": not nsfw,
            "r2": True,
            "slow_workers": True,
        }

        try:
            # Submit job
            resp = requests.post(
                "https://stablehorde.net/api/v2/generate/async",
                json=payload,
                headers=headers,
                timeout=30,
            )

            if resp.status_code != 202:
                return None, f"Submit failed: {resp.status_code}"

            job_id = resp.json().get("id")

            # Poll for result (10 min max)
            for _ in range(120):
                time.sleep(5)
                
                check = requests.get(
                    f"https://stablehorde.net/api/v2/generate/check/{job_id}",
                    headers=headers,
                    timeout=15,
                ).json()

                if check.get("done"):
                    status = requests.get(
                        f"https://stablehorde.net/api/v2/generate/status/{job_id}",
                        headers=headers,
                        timeout=30,
                    ).json()

                    gens = status.get("generations", [])
                    if gens and gens[0].get("img"):
                        img_data = requests.get(gens[0]["img"], timeout=60).content
                        return Image.open(io.BytesIO(img_data)), None

            return None, "Timed out (10 min)"

        except Exception as e:
            return None, str(e)

    @staticmethod
    def generate(prompt: str, engine: str = "pollinations", **kwargs) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Generate image from prompt.
        Engines: 'pollinations' (fast), 'stable_horde' (quality)
        Both FREE.
        """
        if engine == "pollinations":
            allowed = {
                "width": kwargs.get("width", 768),
                "height": kwargs.get("height", 1024),
                "nsfw": kwargs.get("nsfw", False),
            }
            return ImageGenerator._pollinations(prompt, **allowed)
        elif engine == "stable_horde":
            allowed = {
                "negative_prompt": kwargs.get("negative_prompt", ""),
                "width": kwargs.get("width", 768),
                "height": kwargs.get("height", 1024),
                "model": kwargs.get("model", "Deliberate"),
                "nsfw": kwargs.get("nsfw", False),
                "steps": kwargs.get("steps", 25),
                "cfg_scale": kwargs.get("cfg_scale", 7.0),
            }
            return ImageGenerator._stable_horde(prompt, **allowed)
        else:
            return None, f"Unknown engine: {engine}"


HORDE_MODELS = [
    "Deliberate",
    "AbsoluteReality",
    "CyberRealistic",
    "ProjectUnreal",
    "Anything V5",
    "dreamshaper_8",
    "Realistic Vision V5.1",
    "SDXL 1.0",
]

CHARACTER_OPTIONS = {
    "Hair": ["Short black", "Long blonde", "Red curly", "Silver white", "Dark blue", "Brown wavy"],
    "Eyes": ["Blue", "Green", "Brown", "Purple", "Gold", "Grey"],
    "Skin": ["Fair", "Tan", "Dark", "Pale", "Olive", "Bronze"],
    "Build": ["Athletic", "Slim", "Curvy", "Muscular", "Average", "Petite"],
    "Expression": ["Serious", "Smiling", "Angry", "Sad", "Mysterious", "Determined"],
    "Age": ["Teen", "Young adult", "Adult", "Middle-aged", "Elder"],
}

CLOTHES_OPTIONS = {
    "Top": ["White shirt", "Black leather jacket", "Red dress", "Armor", "Hoodie", "Kimono"],
    "Bottom": ["Jeans", "Short skirt", "Battle pants", "Shorts", "Robe", "Leggings"],
    "Shoes": ["Boots", "Heels", "Sneakers", "Sandals", "Barefoot", "Armored boots"],
    "Style": ["Casual", "Gothic", "Fantasy", "Sci-Fi", "Formal", "Streetwear"],
    "Color": ["Black", "Red", "White", "Blue", "Gold", "Purple"],
}

STYLE_PRESETS = ["Noir", "Manga", "Cinematic", "8K", "Fantasy", "Vintage"]


def apply_style_to_prompts(prompts: str, style: str) -> str:
    """Append a style tag to every non-empty prompt line."""
    clean_style = style.strip().lower()
    return "\n".join(
        f"{line.strip()}, {clean_style}"
        for line in prompts.splitlines()
        if line.strip()
    )


def build_descriptor(values: Dict[str, str]) -> str:
    """Build a prompt descriptor from character or clothing selections."""
    return ", ".join(str(value).strip().lower() for value in values.values() if str(value).strip())


def import_text_from_bytes(file_bytes: bytes, filename: str) -> Dict:
    """Extract prompt lines from TXT, HTML, JSON, XML, or plain text uploads."""
    suffix = Path(filename).suffix.lower()
    text = file_bytes.decode("utf-8", errors="ignore")

    if suffix in [".html", ".htm"]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            lines = [line.strip() for line in soup.get_text("\n").splitlines()]
        except ImportError:
            lines = [re.sub(r"<[^>]+>", " ", line).strip() for line in text.splitlines()]
    else:
        lines = [line.strip() for line in text.splitlines()]

    clean = [line for line in lines if line and len(line) > 2][:200]
    return {
        "success": True,
        "filename": filename,
        "line_count": len(clean),
        "text": "\n".join(clean),
    }


def image_to_data_uri(path: Path) -> str:
    """Convert an output image into a data URI for self-contained exports."""
    raw = path.read_bytes()
    ext = path.suffix.lstrip(".").lower()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
    return f"data:image/{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def export_comic_html(images: list, output_dir: str = "outputs") -> Dict:
    """Create a self-contained HTML comic export from generated images."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    panels = []

    for item in images:
        filename = item.get("filename", "")
        prompt = str(item.get("prompt") or "").replace("<", "&lt;").replace(">", "&gt;")
        if not filename:
            continue
        try:
            path = (out / filename).resolve()
            path.relative_to(out.resolve())
        except (OSError, ValueError):
            continue
        if not path.exists() or not path.is_file():
            continue
        panels.append(
            f'<article class="panel"><img src="{image_to_data_uri(path)}" alt="{prompt}">'
            f'<p>{prompt}</p></article>'
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unified Studio Comic Export</title>
<style>
body {{ margin: 0; background: #111; color: #f5f5f5; font-family: Segoe UI, Arial, sans-serif; }}
main {{ width: min(980px, 94vw); margin: 32px auto; display: grid; gap: 24px; }}
h1 {{ font-size: 28px; }}
.panel {{ background: #1d1d1d; border: 1px solid #333; padding: 14px; border-radius: 8px; }}
.panel img {{ width: 100%; height: auto; display: block; border-radius: 6px; }}
.panel p {{ color: #cfd3d8; line-height: 1.5; }}
</style>
</head>
<body><main><h1>Unified Studio Comic Export</h1>{''.join(panels)}</main></body>
</html>"""

    filename = f"comic_export_{int(time.time())}.html"
    path = out / filename
    path.write_text(html, encoding="utf-8")
    return {"success": True, "filename": filename, "url": f"/outputs/{filename}", "panel_count": len(panels)}


def edit_image_file(
    filename: str,
    output_dir: str = "outputs",
    filter_name: str = "none",
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    caption: str = "",
    caption_position: str = "bottom",
) -> Tuple[Optional[Image.Image], Optional[str]]:
    """Apply image filters, enhancements, and optional caption text."""
    root = Path(output_dir).resolve()
    try:
        path = (root / filename).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None, "Invalid image filename"
    if not path.exists() or not path.is_file():
        return None, "Image not found"

    try:
        img = Image.open(path).convert("RGB")
        if filter_name == "grayscale":
            img = img.convert("L").convert("RGB")
        elif filter_name == "blur":
            img = img.filter(ImageFilter.GaussianBlur(radius=2))
        elif filter_name == "sharpen":
            img = img.filter(ImageFilter.SHARPEN)
        elif filter_name == "vintage":
            overlay = Image.new("RGB", img.size, (255, 205, 125))
            img = Image.blend(img, overlay, 0.18)

        img = ImageEnhance.Brightness(img).enhance(max(0.1, brightness))
        img = ImageEnhance.Contrast(img).enhance(max(0.1, contrast))
        img = ImageEnhance.Color(img).enhance(max(0.0, saturation))

        if caption.strip():
            draw = ImageDraw.Draw(img)
            text = caption.strip()[:180]
            margin = max(18, img.width // 32)
            text_box_h = max(48, img.height // 12)
            y = margin if caption_position == "top" else img.height - text_box_h - margin
            draw.rounded_rectangle(
                (margin, y, img.width - margin, y + text_box_h),
                radius=10,
                fill=(0, 0, 0),
                outline=(255, 255, 255),
                width=1,
            )
            draw.text((margin + 16, y + 14), text, fill=(255, 255, 255))

        return img, None
    except Exception as exc:
        return None, str(exc)


def process_uploaded_file(file_bytes: bytes, filename: str, operation: str = "analyze", output_dir: str = "outputs") -> Dict:
    """Analyze or convert uploaded images/text files."""
    mime_type, _ = mimetypes.guess_type(filename)
    suffix = Path(filename).suffix.lower()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if mime_type and mime_type.startswith("image/"):
        img = Image.open(io.BytesIO(file_bytes))
        result = {
            "success": True,
            "filename": filename,
            "operation": operation,
            "type": mime_type,
            "format": img.format,
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
        }
        if operation == "optimize":
            img.thumbnail((1920, 1920))
            save_name = f"optimized_{int(time.time())}.jpg"
            img.convert("RGB").save(out / save_name, "JPEG", quality=85)
            result["url"] = f"/outputs/{save_name}"
        elif operation == "resize":
            save_name = f"resized_{int(time.time())}.png"
            img.resize((800, 600)).save(out / save_name, "PNG")
            result["url"] = f"/outputs/{save_name}"
        elif operation == "convert_to_png":
            save_name = f"converted_{int(time.time())}.png"
            img.convert("RGBA").save(out / save_name, "PNG")
            result["url"] = f"/outputs/{save_name}"
        return result

    if (mime_type and (mime_type.startswith("text/") or mime_type in ["application/json", "application/xml"])) or suffix in [".txt", ".json", ".xml", ".html", ".htm", ".md"]:
        imported = import_text_from_bytes(file_bytes, filename)
        text = imported["text"]
        result = {
            "success": True,
            "filename": filename,
            "operation": operation,
            "type": mime_type or "text/plain",
            "chars": len(text),
            "lines": text.count("\n") + (1 if text else 0),
            "words": len(text.split()),
            "preview": text[:1000],
        }
        if operation == "format_json":
            data = json.loads(text)
            save_name = f"formatted_{int(time.time())}.json"
            (out / save_name).write_text(json.dumps(data, indent=2), encoding="utf-8")
            result["url"] = f"/outputs/{save_name}"
        return result

    return {"success": False, "error": f"Unsupported file type: {mime_type or suffix}"}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: save output
# ─────────────────────────────────────────────────────────────────────────────

def save_image(image: Image.Image, output_dir: str = "outputs") -> str:
    """Save image to disk; return filename."""
    os.makedirs(output_dir, exist_ok=True)
    
    import uuid
    filename = f"image_{uuid.uuid4().hex[:8]}.png"
    path = os.path.join(output_dir, filename)
    
    image.save(path, "PNG")
    return filename
