# ⚡ UNIFIED STUDIO

**Production-ready AI system: Agent + Comic Forge + Image Generation**

Integrated multi-agent AI system combining intelligent chat routing, image generation, web search, and code execution — all using **FREE APIs**.

```
Intel i5-6300U (2.4GHz) | 8GB RAM | 100% Online
```

---

## 🎯 WHAT YOU GET

### 1. **Multi-Agent AI Chat** 💬
- Intelligent request routing (Groq Llama 3.3 70B)
- Specialists for: web search, code, images, general reasoning
- Conversation memory (SQLite)
- WebSocket support for real-time streaming

### 2. **Comic Forge Image Generation** 🎨
- **Pollinations** (fast, free Flux)
- **Stable Horde** (quality, free community power)
- Prompt optimization
- Image gallery & metadata tracking

### 3. **Web Search** 🌐
- Real-time internet search (DuckDuckGo)
- No API key required
- Integrated into agent responses

### 4. **Code Execution** 💻
- Safe Python sandbox
- 10-second timeout
- Security checks (blocks dangerous patterns)

### 5. **Modern Web UI** 🖥️
- Tab-based interface (Chat, Image, Code, Search)
- Dark theme optimized for 8GB RAM
- Responsive design (desktop/tablet/mobile)
- Session management

---

## 🔧 REQUIREMENTS

- **Python 3.10+**
- **8GB RAM** (optimized for your system)
- **Internet connection** (for Groq, image generation, web search)

---

## ⚡ QUICK START (5 minutes)

### Step 1: Install Dependencies
```bash
INSTALL.bat
```
Wait for "Installation complete!"

### Step 2: Set Up Environment
```bash
# Copy example to .env
copy .env.example .env
```

Open `.env` in Notepad and **replace** this line:
```
GROQ_API_KEY=your_groq_api_key_here
```

Get a **free Groq key** (1 minute):
1. Go to: https://console.groq.com
2. Sign up (free)
3. Create API key
4. Paste into `.env`

### Step 3: Start the System
```bash
START_UNIFIED.bat
```

Open your browser to: **http://localhost:5000**

---

## 📋 FEATURES

### Chat Tab 💬
- Type messages → Agent routes to specialists
- Conversation memory
- Export chat as text
- Clear session

**Example prompts:**
- "Search for latest AI news"
- "Write Python code to calculate pi digits"
- "Generate an anime girl with blue hair"
- "Summarize this topic..."

### Image Tab 🎨
- **Two engines:**
  - **Pollinations** (recommended): Fast, Flux model, often 30-60 seconds
  - **Stable Horde**: Quality, may take 2-5 minutes (free community power)
- Adjustable: width, height, NSFW toggle
- Image gallery with metadata

**Tips:**
- Be specific: "a futuristic cyberpunk city at night with flying cars"
- Use negative prompts for refinement
- Try both engines — Pollinations faster, Horde better quality

### Code Tab 💻
- Write & execute Python safely
- Real-time output
- Timeout protection (10 seconds)
- Security checks

**Example:**
```python
import math
for i in range(1, 11):
    print(f"{i}^2 = {i**2}")
```

### Search Tab 🌐
- Query the web (DuckDuckGo)
- No API key needed
- Results with titles, URLs, snippets

---

## 🏗️ ARCHITECTURE

```
UNIFIED_STUDIO/
├── backend/
│   ├── server.py          ← FastAPI server (main)
│   ├── agent.py           ← Multi-agent routing logic
│   ├── tools.py           ← Search, code, image execution
│   ├── memory.py          ← SQLite conversation storage
│   └── __init__.py
├── frontend/
│   ├── index.html         ← Single-page app
│   ├── app.js             ← Client logic
│   └── style.css          ← Dark theme
├── data/                  ← SQLite database (auto-created)
├── outputs/               ← Generated images
├── requirements.txt
├── .env.example
├── INSTALL.bat
└── START_UNIFIED.bat
```

### APISEndpoints

```
POST   /api/chat                 → Send message to agent
GET    /api/history/{session_id} → Get conversation history
POST   /api/generate-image       → Generate image
GET    /api/search?q=query       → Web search
POST   /api/execute-code         → Execute Python
GET    /api/status               → System health
WS     /ws/chat                  → WebSocket real-time chat
```

---

## 💰 COSTS

### **$0/month** ✅

| Service | Cost | Notes |
|---------|------|-------|
| **Groq API** | Free | 9,000 tokens/min tier (plenty) |
| **Pollinations** | Free | No key required |
| **Stable Horde** | Free | Community power, anonymously |
| **DuckDuckGo** | Free | No API key |
| **Database** | Free | Local SQLite |

---

## ⚙️ CONFIGURATION

Edit `.env`:

```env
# Required
GROQ_API_KEY=gsk_...

# Optional (leave as is for anonymous)
HORDE_API_KEY=0000000000

# Server
UNIFIED_PORT=5000
UNIFIED_DB_PATH=data/unified.db
```

---

## 🚀 ADVANCED USAGE

### Run on Different Port
```bash
set UNIFIED_PORT=8080
START_UNIFIED.bat
```

### Access from Network
Change `127.0.0.1` to `0.0.0.0` in `START_UNIFIED.bat`

### Use WebSocket (Real-time Chat)
```javascript
const ws = new WebSocket("ws://localhost:5000/ws/chat");
ws.send(JSON.stringify({ message: "Hello!" }));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

### Backup Conversation
- **Manual:** Chat tab → "Export"
- **Auto:** Check `data/unified.db` (SQLite)

---

## ❓ TROUBLESHOOTING

### "Python not found"
- Install Python 3.10+: https://www.python.org/downloads
- **IMPORTANT:** Check "Add Python to PATH" during install
- Restart terminal after install

### "GROQ_API_KEY not set"
- Did you copy `.env.example` to `.env`?
- Did you add your key? (Should start with `gsk_`)
- Test: `cat .env` (Windows: `type .env`)

### "Server won't start"
- Other app using port 5000?
  - Change in `.env`: `UNIFIED_PORT=8080`
- Firewall blocking?
  - Allow Python through Windows Firewall

### "Images generating very slowly"
- Stable Horde is free but slow (2-5 min)
- Switch to Pollinations (30-60 sec)
- DuckDuckGo rate-limited? Wait 30 sec

### "Chat not responding"
- Check Groq API key is valid
- Check internet connection
- Check firewall/proxy settings

---

## 📊 PERFORMANCE (Your Hardware)

```
System: Intel i5-6300U, 8GB RAM

Typical Response Times:
├─ Chat message:      1-3 seconds
├─ Web search:        2-5 seconds
├─ Image (Flux):      30-60 seconds
├─ Image (Horde):     2-5 minutes
└─ Code execution:    <1 second
```

Optimizations applied:
- SQLite with WAL mode (concurrent access)
- Connection pooling for memory efficiency
- Async FastAPI for non-blocking I/O
- Security timeouts (10s code execution)

---

## 🔒 SECURITY & PRIVACY

✅ **What's private:**
- Conversations stored locally in SQLite
- No data sent to external servers except:
  - Groq API (for LLM inference)
  - Stable Horde / Pollinations (for images)
  - DuckDuckGo (for search)

✅ **Code sandboxing:**
- Blocks dangerous patterns: `os.system`, `exec`, `eval`
- 10-second execution timeout
- Subprocess isolation

---

## 📚 EXAMPLES

### Generate a Comic Panel
1. Go to **Image Tab**
2. Enter: `"detailed anime, comic panel style, girl with red hair, cyberpunk city background, cinematic lighting, high quality"`
3. Set: Pollinations engine, 768x1024
4. Click "Generate Image"
5. Save from gallery

### Write & Run a Script
1. Go to **Code Tab**
2. Paste Python code
3. Click "Execute"
4. See output instantly

### Ask Complex Questions
1. Go to **Chat Tab**
2. Ask: "What was the latest breakthrough in AI this month?"
3. Agent uses web search + Groq reasoning
4. Get synthesized, current answer

---

## 📞 SUPPORT

### Getting Help
- **Groq API issues:** https://console.groq.com/docs
- **Stable Horde issues:** https://stablehorde.net
- **Python/Code issues:** Check error message + restart

### Check System Health
- Visit: http://localhost:5000/api/status
- Should show: `"status": "healthy"`

---

## 🎓 LEARNING

Inspect these to understand the system:

1. **`backend/agent.py`** — Agent routing logic
2. **`backend/tools.py`** — Tool implementations
3. **`frontend/app.js`** — Client-side interactions
4. **`backend/server.py`** — API endpoints

---

## 📜 LICENSE

Free to use, modify, and distribute. No restrictions.

---

## 🔮 FUTURE ENHANCEMENTS

Potential additions (no breaking changes):
- Local LLM fallback (Ollama)
- Voice input/output
- Batch image generation
- Custom agent creation UI
- Plugin system

---

**Built for your i5-6300U. Tested. Production-ready. 100% Free.** ⚡


## Mobile / LAN Mode

Use `START_MOBILE.bat` to expose the touch-optimized Unified Studio UI to a phone or tablet on the same private LAN. The launcher prints the LAN URL. Do not expose port 5000 to the public internet.
