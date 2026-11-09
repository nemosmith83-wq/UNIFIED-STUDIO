import glob
import importlib.machinery
import importlib.util
import os
import secrets
import socket
import sys
import threading
import time

_server = None
_thread = None


def _load_bundled_module(module_name, bytecode_dir):
    """Load a Python 3.13 bytecode-only module shipped in Android assets."""
    if module_name in sys.modules:
        return sys.modules[module_name]

    pattern = os.path.join(bytecode_dir, f"{module_name}.*.pyc")
    candidates = sorted(glob.glob(pattern))
    if not candidates:
        raise RuntimeError(
            f"Required Android module '{module_name}' is missing from bundled bytecode."
        )

    expected_tag = f"cpython-{sys.version_info.major}{sys.version_info.minor}"
    compatible = [path for path in candidates if expected_tag in os.path.basename(path)]
    if not compatible:
        raise RuntimeError(
            f"No compatible bytecode for '{module_name}'. "
            f"This app requires {expected_tag}; found: {', '.join(os.path.basename(p) for p in candidates)}"
        )

    module_path = compatible[0]
    with open(module_path, "rb") as module_file:
        magic = module_file.read(4)
    if magic != importlib.util.MAGIC_NUMBER:
        raise RuntimeError(f"Bundled bytecode for '{module_name}' has an incompatible Python magic number.")

    loader = importlib.machinery.SourcelessFileLoader(module_name, module_path)
    spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None:
        raise RuntimeError(f"Could not create an import specification for '{module_name}'.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _load_or_create_secret(path, min_length=32):
    """Persist per-install admin secrets in the app-private data directory."""
    try:
        with open(path, "r", encoding="utf-8") as secret_file:
            value = secret_file.read().strip()
        if len(value) >= min_length:
            return value
    except OSError:
        pass

    value = secrets.token_urlsafe(48)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as secret_file:
        secret_file.write(value)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return value


def start_server(
    frontend_dir,
    outputs_dir,
    db_path,
    bytecode_dir=None,
    host="127.0.0.1",
    port=8765,
):
    global _server, _thread
    if _thread and _thread.is_alive():
        return {"status": "running", "url": f"http://{host}:{port}/"}

    os.environ["UNIFIED_FRONTEND_DIR"] = str(frontend_dir)
    os.environ["UNIFIED_OUTPUTS_DIR"] = str(outputs_dir)
    os.environ["UNIFIED_DB_PATH"] = str(db_path)
    os.environ["UNIFIED_ROOT_DIR"] = str(os.path.dirname(frontend_dir))
    os.environ["UNIFIED_ANDROID"] = "1"

    private_dir = os.path.dirname(os.path.abspath(db_path))
    os.environ.setdefault("UVS_DB_PATH", os.path.join(private_dir, "uvs_admin.db"))
    os.environ.setdefault("UVS_TOKEN_SECRET", _load_or_create_secret(os.path.join(private_dir, "uvs_token_secret.txt")))
    os.environ.setdefault("UVS_ADMIN_SETUP_KEY", _load_or_create_secret(os.path.join(private_dir, "uvs_admin_setup_key.txt")))

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    if bytecode_dir:
        bytecode_dir = os.path.abspath(bytecode_dir)
        for module_name in ("memory", "agent", "talent"):
            _load_bundled_module(module_name, bytecode_dir)

    import server
    import uvicorn

    config = uvicorn.Config(
        server.app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    _server = uvicorn.Server(config)

    def run():
        _server.run()

    _thread = threading.Thread(target=run, name="UnifiedStudioServer", daemon=True)
    _thread.start()

    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return {"status": "running", "url": f"http://{host}:{port}/"}
        except OSError:
            if _thread is not None and not _thread.is_alive():
                return {"status": "failed", "error": "Unified Studio server thread exited during startup."}
            time.sleep(0.25)

    return {"status": "failed", "error": "Unified Studio server did not open its local port within 15 seconds."}


def stop_server():
    global _server
    if _server:
        _server.should_exit = True
    return {"status": "stopping"}
