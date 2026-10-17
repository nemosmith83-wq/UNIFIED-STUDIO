"""
Unified Studio Backend — Multi-agent AI system
Integrates: Agent (Groq), Image Generation (Pollinations + Stable Horde), Web Search (DuckDuckGo)
All FREE. Optimized for 8GB RAM.
"""

__version__ = "1.0.0"
__author__ = "Unified Studio"

import os
from pathlib import Path

# Ensure data directory exists
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Initialize database on import
from . import memory
memory.init_db()
