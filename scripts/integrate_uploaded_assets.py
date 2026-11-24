#!/usr/bin/env python3
"""Integrate and validate the uploaded studio collection before APK packaging."""
from __future__ import annotations
import json
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

repo = Path(__import__("os").environ["GITHUB_WORKSPACE"])
project = Path(sys.argv[1])
frontend = project / "app/src/main/assets/frontend"
source_studios = repo / "frontend/user_studios"
target_studios = frontend / "user_studios"

shutil.copytree(source_studios, target_studios, dirs_exist_ok=True)

manifest_path = target_studios / "uploaded-assets-manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("sourceUploadCount") != 20 or len(manifest.get("files", [])) != 20:
    raise SystemExit("Uploaded assets manifest must account for all 20 source files.")

# Strip references to the optional shared helper, which is not shipped in this app.
core_pattern = re.compile(
    r'<script\\b[^>]*\\bsrc=["\\'][^"\\']*uvs-core\\.js[^"\\']*["\\'][^>]*>\\s*</script>',
    re.I,
)
roots = [frontend / "new-era/tools", target_studios]
removed = {}
for root in roots:
    count_total = 0
    for page in root.rglob("*.html"):
        original = page.read_text(encoding="utf-8")
        updated, count = core_pattern.subn("", original)
        if count:
            page.write_text(updated, encoding="utf-8")
            count_total += count
    removed[root.name] = count_total
if removed.get("tools") != 8:
    raise SystemExit(f"Expected 8 optional uvs-core refs in New Era tools, removed {removed.get('tools')}.")

# Fix invalid lookbehind quantifier in both XTTS copies.
bad = r"(?<=[.!?؟।\\n])+"
good = r"(?<=[.!?؟।\\n])"
for page in [
    frontend / "new-era/tools/XTTS_v2_Bilingual_Voice_Studio.html",
    target_studios / "uploaded/XTTS_v2_Bilingual_Voice_Studio.html",
]:
    if page.exists():
        text = page.read_text(encoding="utf-8")
        text = text.replace(bad, good)
        if bad in text:
            raise SystemExit(f"Invalid XTTS sentence-splitting regex remains in {page}")
        page.write_text(text, encoding="utf-8")

class HTMLAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.scripts = []
        self.current = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "script":
            self.current = [attrs.get("type", "").lower(), ""]
        for key in ("src", "href"):
            value = attrs.get(key)
            if value:
                self.refs.append(value)
    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data
    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current is not None:
            self.scripts.append(self.current)
            self.current = None

pages = sorted((target_studios / "uploaded").glob("*.html"))
if len(pages) < 18:
    raise SystemExit(f"Expected at least 18 uploaded HTML pages, found {len(pages)}.")
pages.append(target_studios / "uploaded-assets.html")
errors = []
for page in pages:
    parser = HTMLAudit()
    parser.feed(page.read_text(encoding="utf-8"))
    for ref in parser.refs:
        if ref.startswith(("http:", "https:", "//", "data:", "blob:", "#", "javascript:", "mailto:", "tel:")):
            continue
        parsed = urlsplit(ref)
        rel = parsed.path
        if not rel:
            continue
        target = (frontend / rel.lstrip("/")) if rel.startswith("/") else (page.parent / rel)
        target = target.resolve()
        if not target.exists() and not (target.is_dir() and (target / "index.html").exists()):
            errors.append(f"{page.relative_to(frontend)}: missing local reference {ref}")
    for i, (kind, code) in enumerate(parser.scripts):
        if not code.strip() or kind in ("importmap", "application/ld+json", "application/json", "text/plain"):
            continue
        suffix = ".mjs" if kind == "module" else ".js"
        with tempfile.NamedTemporaryFile("w", suffix=suffix, encoding="utf-8", delete=False) as temp:
            temp.write(code)
            temp_path = Path(temp.name)
        check = subprocess.run(["node", "--check", str(temp_path)], capture_output=True, text=True)
        temp_path.unlink(missing_ok=True)
        if check.returncode:
            tail = check.stderr.splitlines()[-1] if check.stderr else "syntax error"
            errors.append(f"{page.name} inline script {i}: {tail}")
if errors:
    raise SystemExit("\\n".join(errors[:50]))

# Add both library entries to the app's main navigation without removing existing tabs.
index = frontend / "index.html"
text = index.read_text(encoding="utf-8")
links = [
    '<a class="nav-btn" href="/new-era/unified-launcher.html">FadeL The New Era + Tools</a>',
    '<a class="nav-btn" href="/user_studios/uploaded-assets.html">Uploaded Assets Library</a>',
]
for link in links:
    if link in text:
        continue
    nav_start = text.find('<nav class="nav-tabs">')
    if nav_start >= 0:
        nav_end = text.find("</nav>", nav_start)
        if nav_end < 0:
            raise SystemExit("Main navigation closing tag not found.")
        text = text[:nav_end] + link + text[nav_end:]
    else:
        text = text.replace("</body>", link + "</body>")
index.write_text(text, encoding="utf-8")

required = [
    "uploaded-assets.html",
    "uploaded-assets-manifest.json",
    "uploaded/Flux2_Klein_FaceSwap_Studio_v14.html",
    "uploaded/Remake_AI_FaceSwap_v8_Studio.html",
    "uploaded/Stable_Diffusion_Mobile_PRO_v11_Flux_IPAdapter.html",
    "uploaded/comic_factory_full.html",
    "uploaded/uvs-vault-2026-11-18.json",
    "uploaded/The_New_Era_Complete_Colab_APK_Factory.ipynb",
]
for rel in required:
    if not (target_studios / rel).is_file():
        raise SystemExit(f"Required uploaded asset missing: {rel}")
print(f"Integrated {len(pages)-1} uploaded HTML pages; removed optional shared-core refs {removed}; local links and inline JS syntax passed.")
