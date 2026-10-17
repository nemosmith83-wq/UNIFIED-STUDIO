"""Initialize the local Unified Studio configuration."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def main() -> int:
    print("\n" + "=" * 70)
    print("  UNIFIED STUDIO — LOCAL SETUP")
    print("=" * 70)
    if ENV.exists():
        print(f"\n✅ .env already exists: {ENV}")
    elif EXAMPLE.exists():
        shutil.copy2(EXAMPLE, ENV)
        print(f"\n✅ Created .env from .env.example")
    else:
        print("\n❌ .env.example is missing")
        return 1
    print("✅ No LLM API key is required. Unified Studio uses local Ollama.")
    print("   Optional Stable Horde access is configured through HORDE_API_KEY.")
    print("\n🚀 Next: run START.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
