import os, json, sqlite3, urllib.request, urllib.error
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(APP_DIR, "content_studio.db"))
app = Flask(__name__)
scheduler = BackgroundScheduler(daemon=True)

def db():
    c = sqlite3.connect(DB_PATH, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, channel TEXT DEFAULT 'General', status TEXT DEFAULT 'Idea', body TEXT DEFAULT '', scheduled_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS guidelines(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT NOT NULL, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS agent_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        if not c.execute("SELECT 1 FROM guidelines LIMIT 1").fetchone():
            c.execute("INSERT INTO guidelines(title,content) VALUES(?,?)", ("Brand voice", "Write clear, useful, audience-first content. Avoid unsupported claims. Match the channel and brand voice supplied by the owner."))
        if not c.execute("SELECT 1 FROM items LIMIT 1").fetchone():
            now=datetime.utcnow().isoformat(timespec="minutes")
            c.execute("INSERT INTO items(title,channel,status,body,created_at,updated_at) VALUES(?,?,?,?,?,?)", ("Welcome — add your first idea","General","Idea","",now,now))

def log(action, detail, agent="Content Agent"):
    with db() as c:
        c.execute("INSERT INTO agent_logs(agent,action,detail,created_at) VALUES(?,?,?,?)",(agent,action,detail,datetime.utcnow().isoformat(timespec="seconds")))

def ai(prompt, system="You are a professional commercial content strategist and copywriter."):
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key:
        return None, "Set OPENAI_API_KEY in the environment to enable AI generation."
    base=os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1").rstrip("/")
    model=os.getenv("OPENAI_MODEL","gpt-4o-mini")
    payload=json.dumps({"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":prompt}],"temperature":0.7}).encode()
    req=urllib.request.Request(base+"/chat/completions",data=payload,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=90) as res:
            data=json.loads(res.read().decode())
        return data["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, "AI provider error: "+str(e)

def context():
    with db() as c:
        guidelines=[r["title"]+": "+r["content"] for r in c.execute("SELECT title,content FROM guidelines WHERE active=1")]
        published=[r["title"]+" ["+r["channel"]+"]: "+r["body"][:1200] for r in c.execute("SELECT title,channel,body FROM items WHERE status='Published' ORDER BY id DESC LIMIT 8")]
    return "\n".join(["GUIDELINES:",*guidelines,"PUBLISHED EXAMPLES:",*published])

def weekly_plan():
    with db() as c:
        ideas=[r["title"] for r in c.execute("SELECT title FROM items WHERE status IN ('Idea','Draft') ORDER BY id DESC LIMIT 12")]
    prompt="Create a practical 7-day content plan. Use these existing ideas when relevant: "+", ".join(ideas)+"\nReturn day, channel, topic and objective for each day."
    result,err=ai(prompt,context())
    if not result:
        result="Weekly plan needs AI configuration. Suggested starter cadence: Mon educational post; Tue product benefit; Wed customer question; Thu behind-the-scenes; Fri offer or CTA; Sat community post; Sun weekly recap."
    with db() as c:
        now=datetime.utcnow().isoformat(timespec="seconds")
        c.execute("INSERT INTO items(title,channel,status,body,scheduled_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",("Weekly content plan","Planning","Review",result,(datetime.utcnow()+timedelta(days=1)).isoformat(timespec="minutes"),now,now))
    log("Weekly plan created",result[:500],"Scheduled Content Agent")

def daily_report():
    with db() as c:
        rows=c.execute("SELECT status,COUNT(*) n FROM items GROUP BY status").fetchall()
        summary=", ".join([r["status"]+": "+str(r["n"]) for r in rows]) or "No content items"
    log("Daily queue report",summary,"Scheduled Content Agent")

@app.get("/")
def home():
    return render_template_string(PAGE)

@app.get("/api/items")
def list_items():
    with db() as c: rows=c.execute("SELECT * FROM items ORDER BY updated_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.post("/api/items")
def create_item():
    d=request.get_json(force=True); now=datetime.utcnow().isoformat(timespec="minutes")
    if not d.get("title","").strip(): return jsonify(error="Title is required"),400
    with db() as c:
        cur=c.execute("INSERT INTO items(title,channel,status,body,scheduled_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(d["title"].strip(),d.get("channel","General"),d.get("status","Idea"),d.get("body",""),d.get("scheduled_at") or None,now,now))
        ident=cur.lastrowid
    log("Item created",d["title"])
    return jsonify(id=ident),201

@app.patch("/api/items/<int:ident>")
def update_item(ident):
    d=request.get_json(force=True); allowed={"title","channel","status","body","scheduled_at"}
    sets=[k+"=?" for k in d if k in allowed]; vals=[d[k] for k in d if k in allowed]
    if not sets:return jsonify(error="No valid fields"),400
    sets.append("updated_at=?");vals.append(datetime.utcnow().isoformat(timespec="minutes"));vals.append(ident)
    with db() as c:c.execute("UPDATE items SET "+",".join(sets)+" WHERE id=?",vals)
    log("Item updated","Item #"+str(ident))
    return jsonify(ok=True)

@app.delete("/api/items/<int:ident>")
def delete_item(ident):
    with db() as c:c.execute("DELETE FROM items WHERE id=?",(ident,))
    log("Item deleted","Item #"+str(ident))
    return jsonify(ok=True)

@app.get("/api/guidelines")
def list_guidelines():
    with db() as c: rows=c.execute("SELECT * FROM guidelines ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])

@app.post("/api/guidelines")
def add_guideline():
    d=request.get_json(force=True)
    if not d.get("title") or not d.get("content"):return jsonify(error="Title and content required"),400
    with db() as c:cur=c.execute("INSERT INTO guidelines(title,content,active) VALUES(?,?,1)",(d["title"],d["content"]))
    log("Guideline added",d["title"])
    return jsonify(id=cur.lastrowid),201

@app.post("/api/generate")
def generate():
    d=request.get_json(force=True); kind=d.get("kind","draft"); topic=d.get("topic","")
    if not topic.strip():return jsonify(error="Enter a topic or idea"),400
    prompt=("Create a concise content outline for: " if kind=="outline" else "Write a polished first draft for: ")+topic+"\nChannel: "+d.get("channel","General")+"\nInclude a clear hook, useful body, and appropriate CTA. Do not invent factual claims.\n"+context()
    result,err=ai(prompt)
    if not result:return jsonify(error=err),503
    log(kind+" generated",topic)
    return jsonify(content=result)

@app.post("/api/weekly-plan")
def run_weekly():
    weekly_plan()
    return jsonify(ok=True)

@app.get("/api/logs")
def logs():
    with db() as c: rows=c.execute("SELECT * FROM agent_logs ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])

@app.get("/api/health")
def health():return jsonify(status="ok",ai_configured=bool(os.getenv("OPENAI_API_KEY")),database=DB_PATH)

PAGE="""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Content Studio Agent</title><style>
:root{--bg:#0c1020;--panel:#171d31;--line:#29324d;--text:#eef2ff;--muted:#a5b0cc;--accent:#8b9cff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px system-ui}header{padding:24px 5vw;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}h1{margin:0;font-size:24px}small,.muted{color:var(--muted)}main{max-width:1200px;margin:24px auto;padding:0 20px}.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:18px}h2{font-size:17px;margin:0 0 14px}input,select,textarea{width:100%;background:#0e1426;border:1px solid var(--line);border-radius:9px;color:var(--text);padding:11px;margin:6px 0 10px;font:inherit}textarea{min-height:100px;resize:vertical}button{background:var(--accent);color:#10152a;border:0;border-radius:9px;padding:10px 14px;font-weight:700;cursor:pointer;margin:3px}button.secondary{background:#283451;color:var(--text)}.item{border:1px solid var(--line);border-radius:12px;padding:12px;margin:10px 0}.item h3{margin:0 0 6px;font-size:16px}.tag{font-size:12px;color:#cbd5ff}.row{display:flex;gap:8px}.row>*{flex:1}.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}.hidden{display:none}.log{padding:8px;border-bottom:1px solid var(--line);font-size:13px}.status{font-size:12px;color:var(--muted)}@media(max-width:800px){.grid{grid-template-columns:1fr}header{padding:18px 20px}}</style></head><body>
<header><div><h1>Content Studio <span class="tag">AI AGENT</span></h1><small>Ideas → Drafts → Reviews → Published</small></div><button onclick="weekly()">Run weekly plan</button></header><main>
<div class="grid"><section><div class="panel"><h2>New content item</h2><input id="title" placeholder="Content idea / title"><div class="row"><select id="channel"><option>General</option><option>Instagram</option><option>Facebook</option><option>LinkedIn</option><option>TikTok</option><option>Email</option><option>Blog</option></select><select id="itemStatus"><option>Idea</option><option>Draft</option><option>Review</option><option>Published</option></select></div><textarea id="body" placeholder="Brief, draft, notes, or published example"></textarea><input id="date" type="datetime-local"><button onclick="save()">Save item</button><span id="msg" class="status"></span></div>
<div class="panel"><h2>AI writing agent</h2><input id="topic" placeholder="What should the agent write about?"><select id="genChannel"><option>General</option><option>Instagram</option><option>Facebook</option><option>LinkedIn</option><option>TikTok</option><option>Email</option><option>Blog</option></select><div class="row"><button onclick="generate('outline')">Create outline</button><button onclick="generate('draft')">Write first draft</button></div><textarea id="generated" placeholder="Generated content appears here"></textarea><button class="secondary" onclick="saveGenerated()">Save as draft</button><div id="genmsg" class="status"></div></div>
<div class="panel"><h2>Brand guidelines</h2><input id="gtitle" placeholder="Guideline title"><textarea id="gcontent" placeholder="Tone, audience, do/don't rules"></textarea><button onclick="addGuideline()">Add guideline</button><div id="guidelines"></div></div></section>
<section><div class="panel"><h2>Editorial queue</h2><div class="tabs"><button class="secondary" onclick="filter='All';load()">All</button><button class="secondary" onclick="filter='Idea';load()">Ideas</button><button class="secondary" onclick="filter='Draft';load()">Drafts</button><button class="secondary" onclick="filter='Review';load()">Reviews</button><button class="secondary" onclick="filter='Published';load()">Published</button></div><div id="items"></div></div><div class="panel"><h2>Agent activity log</h2><div id="logs"></div></div></section></div></main>
<script>
let filter='All',items=[];
async function api(path,method='GET',data){let r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});let j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j}
async function load(){items=await api('/api/items');document.getElementById('items').innerHTML=items.filter(x=>filter==='All'||x.status===filter).map(x=>'<div class="item"><h3>'+esc(x.title)+'</h3><div class="tag">'+esc(x.channel)+' · '+esc(x.status)+(x.scheduled_at?' · '+esc(x.scheduled_at):'')+'</div><p>'+esc((x.body||'').slice(0,240))+'</p><select id="st'+x.id+'"><option>'+esc(x.status)+'</option><option>Idea</option><option>Draft</option><option>Review</option><option>Published</option></select><button onclick="setStatus('+x.id+')">Update status</button><button class="secondary" onclick="del('+x.id+')">Delete</button></div>').join('')||'<p class="muted">No items in this view.</p>';loadLogs()}
async function save(){try{let d={title:title.value,channel:channel.value,status:itemStatus.value,body:body.value,scheduled_at:date.value};await api('/api/items','POST',d);msg.textContent='Saved';title.value='';body.value='';await load()}catch(e){msg.textContent=e.message}}
async function setStatus(id){await api('/api/items/'+id,'PATCH',{status:document.getElementById('st'+id).value});load()}
async function del(id){if(confirm('Delete this content item?')){await api('/api/items/'+id,'DELETE');load()}}
async function generate(kind){genmsg.textContent='Working…';try{let r=await api('/api/generate','POST',{kind,topic:topic.value,channel:genChannel.value});generated.value=r.content;genmsg.textContent='Generated. Review before publishing.'}catch(e){genmsg.textContent=e.message}}
async function saveGenerated(){await api('/api/items','POST',{title:topic.value||'AI draft',channel:genChannel.value,status:'Draft',body:generated.value});load()}
async function weekly(){try{await api('/api/weekly-plan','POST',{});alert('Weekly plan added to Review queue');load()}catch(e){alert(e.message)}}
async function addGuideline(){try{await api('/api/guidelines','POST',{title:gtitle.value,content:gcontent.value});gtitle.value='';gcontent.value='';loadGuidelines()}catch(e){alert(e.message)}}
async function loadGuidelines(){let g=await api('/api/guidelines');guidelines.innerHTML=g.map(x=>'<div class="log"><b>'+esc(x.title)+'</b><p>'+esc(x.content)+'</p></div>').join('')}
async function loadLogs(){let l=await api('/api/logs');logs.innerHTML=l.slice(0,12).map(x=>'<div class="log"><b>'+esc(x.action)+'</b> · '+esc(x.agent)+'<br><span class="muted">'+esc(x.created_at)+' — '+esc(x.detail)+'</span></div>').join('')}
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
load();loadGuidelines();
</script></body></html>"""

if __name__=="__main__":
    init_db()
    scheduler.add_job(weekly_plan,"cron",day_of_week="mon",hour=9,minute=0,id="weekly_content_plan",replace_existing=True)
    scheduler.add_job(daily_report,"cron",hour=17,minute=30,id="daily_content_report",replace_existing=True)
    scheduler.start()
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","8080")))
