# UNIFIED STUDIO — QUICK START GUIDE

## 📋 Setup (3 simple steps)

### 1️⃣ Install
Double-click: **INSTALL.bat**

Wait until it says "Installation complete!" and press any key.

### 2️⃣ Configure
1. Right-click `.env.example` → "Open with Notepad"
2. Copy all the content
3. Create new file named `.env` in the same folder
4. Paste the content
5. Find this line:
```
GROQ_API_KEY=your_groq_api_key_here
```

6. Replace with your actual key:
```
GROQ_API_KEY=gsk_abc123def456...
```

**How to get your GROQ_API_KEY:**
- Visit: https://console.groq.com
- Click "Sign Up" (or sign in)
- Click "API Keys"
- Click "Create API Key"
- Copy the key (starts with `gsk_`)
- Paste into `.env`

### 3️⃣ Run
Double-click: **START_UNIFIED.bat**

Wait for the server to start (you'll see "Uvicorn running on..."), then:
- **Browser opens automatically** to: http://localhost:5000
- Or manually open: http://127.0.0.1:5000

---

## 💬 What Can You Do?

| Tab | What | How |
|-----|------|-----|
| **Chat** | Talk to AI about anything | Type → Send |
| **Image** | Generate images from text | Describe → Generate |
| **Code** | Write & run Python | Paste code → Execute |
| **Search** | Find info online | Enter query → Search |

---

## ⚠️ If Something Breaks

**Run this first:**
```bash
VALIDATE.bat
```

This checks everything and tells you what's wrong.

---

## 🚨 Common Issues

### "Python not found"
- Download from: https://www.python.org/downloads
- Version: 3.10 or newer
- **Important:** Check "Add Python to PATH" during install

### "Server won't start"
- Did you run INSTALL.bat?
- Did you create .env file?
- Did you add GROQ_API_KEY to .env?

### "API Key invalid"
- Copy the ENTIRE key from console.groq.com
- Should start with `gsk_`
- No spaces at beginning or end

### "Images won't generate"
- Check internet connection
- Try Pollinations first (faster)
- Stable Horde is slower but free

---

## 🎓 First Things to Try

1. **Ask a question:**
   - Type: "What's today's weather?"
   - Agent will search the web for you

2. **Generate an image:**
   - Type: "an astronaut on the moon"
   - Watch as image generates

3. **Run some code:**
   - Paste: 
     ```python
     for i in range(1, 6):
         print(i ** 2)
     ```
   - See output

---

## 📞 Need Help?

- System status: http://localhost:5000/api/status
- Browser console: Press F12 to see errors
- Run validation: VALIDATE.bat

---

**You're all set! Have fun!** 🚀
