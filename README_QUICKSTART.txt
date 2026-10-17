╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                       🚀 UNIFIED STUDIO - QUICKSTART 🚀                      ║
║                                                                              ║
║                        NO API KEYS • 100% FREE • LOCAL AI                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


════════════════════════════════════════════════════════════════════════════════
  THREE STEPS TO GET RUNNING
════════════════════════════════════════════════════════════════════════════════

  STEP 1️⃣  Download Ollama
  ────────────────────────────────────────────────────────────────────────
  
  Go to: https://ollama.ai
  
  Click "Download" → Run installer → Done
  
  Takes: ~2 minutes


  STEP 2️⃣  Run Setup
  ────────────────────────────────────────────────────────────────────────
  
  Double-click: SETUP_OLLAMA.bat
  
  (This downloads the Mistral AI model ~5GB, one-time only)
  
  Takes: ~5 minutes


  STEP 3️⃣  Launch Studio  
  ────────────────────────────────────────────────────────────────────────
  
  Double-click: START.bat
  
  Browser opens → Use the web UI
  
  Takes: ~5 seconds


════════════════════════════════════════════════════════════════════════════════
  WHAT YOU GET
════════════════════════════════════════════════════════════════════════════════

  ✅ Chat with AI (runs LOCAL on your computer)
  ✅ Generate images (FREE via Pollinations)
  ✅ Edit images (draw, erase, pick colors)
  ✅ Run Python code (sandboxed, safe)
  ✅ Search the web (FREE via DuckDuckGo)
  ✅ Save conversation history

  → Zero API keys
  → Zero subscriptions
  → Zero cloud


════════════════════════════════════════════════════════════════════════════════
  FILE REFERENCE
════════════════════════════════════════════════════════════════════════════════

  START.bat                 ← Run this to launch (every time)
  SETUP_OLLAMA.bat          ← Run this first-time setup (after Ollama install)
  OLLAMA_SETUP.txt          ← Detailed setup guide
  .env                      ← Configuration (Ollama URL, model)
  .env.example              ← Template config
  
  backend/                  ← Python server code
  frontend/                 ← Web UI code
  data/                     ← Conversation history (local SQLite)


════════════════════════════════════════════════════════════════════════════════
  TROUBLESHOOTING
════════════════════════════════════════════════════════════════════════════════

  ❌ "Ollama not found"
     → Install from https://ollama.ai first

  ❌ "Can't connect to Ollama"
     → Open terminal and run: ollama serve
        (keep this terminal open while using Unified Studio)

  ❌ "Port 5000 in use"
     → Edit START.bat line: set UNIFIED_PORT=5001

  ❌ "Model download stalled"
     → Run in terminal: ollama pull mistral


════════════════════════════════════════════════════════════════════════════════
  WHY OLLAMA?
════════════════════════════════════════════════════════════════════════════════

  BEFORE (Groq):
  • "Free" but required signup at console.groq.com
  • API key in config
  • Data sent to cloud

  NOW (Ollama):
  • Actually FREE (no signup, no keys)
  • Runs on YOUR computer
  • Data never leaves your machine
  • Works offline (no internet needed)
  • Open source


════════════════════════════════════════════════════════════════════════════════
  QUICK FACTS
════════════════════════════════════════════════════════════════════════════════

  Ollama:       Open-source AI runtime
  Mistral:      7B parameter model (fast, good quality)
  Download:     ~5GB (one time)
  Memory:       Works on 8GB RAM
  Speed:        ~5-10 second responses on i5 processor
  Internet:     Needed for image gen & search (not for chat)


════════════════════════════════════════════════════════════════════════════════
  NEXT STEPS
════════════════════════════════════════════════════════════════════════════════

  1. Click: START_COMIC_FORGE_ULTIMATE.bat (to test)
  2. Download: https://ollama.ai
  3. Run: SETUP_OLLAMA.bat
  4. Run: START.bat
  5. Use the web UI!

═══════════════════════════════════════════════════════════════════════════════
