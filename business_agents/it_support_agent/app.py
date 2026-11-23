import os,json,sqlite3,urllib.request
from datetime import datetime
from flask import Flask,request,jsonify,render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
ROOT=os.path.dirname(os.path.abspath(__file__));DB=os.getenv("DATABASE_PATH",os.path.join(ROOT,"it_support.db"));app=Flask(__name__);sched=BackgroundScheduler(daemon=True)
def conn():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute("PRAGMA journal_mode=WAL");return c
def init():
 with conn() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL,requester TEXT DEFAULT '',priority TEXT DEFAULT 'Normal',status TEXT DEFAULT 'Open',category TEXT DEFAULT 'Other',owner TEXT DEFAULT '',suggested_fix TEXT DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS fixes(id INTEGER PRIMARY KEY,title TEXT NOT NULL,symptoms TEXT NOT NULL,solution TEXT NOT NULL,verified INTEGER DEFAULT 0,created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY,name TEXT NOT NULL,tag TEXT UNIQUE,kind TEXT DEFAULT 'Computer',assigned_to TEXT DEFAULT '',status TEXT DEFAULT 'Active',notes TEXT DEFAULT '');
  CREATE TABLE IF NOT EXISTS known(id INTEGER PRIMARY KEY,title TEXT NOT NULL,details TEXT NOT NULL,workaround TEXT DEFAULT '',active INTEGER DEFAULT 1);
  CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY,agent TEXT,action TEXT,detail TEXT,created_at TEXT);""")
  if not c.execute("SELECT 1 FROM known LIMIT 1").fetchone():c.execute("INSERT INTO known(title,details,workaround) VALUES(?,?,?)",("Sample known issue","Replace this example with a real recurring issue.","Document the safe workaround and escalation path."))
def log(action,detail,agent="IT Support Agent"):
 with conn() as c:c.execute("INSERT INTO logs(agent,action,detail,created_at) VALUES(?,?,?,?)",(agent,action,detail,datetime.utcnow().isoformat(timespec="seconds")))
def knowledge():
 with conn() as c:
  f=[dict(x) for x in c.execute("SELECT title,symptoms,solution,verified FROM fixes ORDER BY verified DESC,id DESC LIMIT 30")]
  k=[dict(x) for x in c.execute("SELECT title,details,workaround FROM known WHERE active=1")]
 return "FIXES:\n"+json.dumps(f,ensure_ascii=False)+"\nKNOWN ISSUES:\n"+json.dumps(k,ensure_ascii=False)
def call_ai(prompt,system):
 key=os.getenv("OPENAI_API_KEY","").strip()
 if not key:return None,"OPENAI_API_KEY is not configured"
 url=os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1").rstrip("/")+"/chat/completions"
 data=json.dumps({"model":os.getenv("OPENAI_MODEL","gpt-4o-mini"),"messages":[{"role":"system","content":system},{"role":"user","content":prompt}],"temperature":0.2}).encode()
 try:
  req=urllib.request.Request(url,data=data,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
  with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode())["choices"][0]["message"]["content"],None
 except Exception as e:return None,"AI provider error: "+str(e)
def triage(id):
 with conn() as c:t=c.execute("SELECT * FROM tickets WHERE id=?",(id,)).fetchone()
 if not t:return None
 prompt="Triage ticket; return JSON with category, priority (Low/Normal/High/Critical), suggested_fix, owner_role. Never claim to have executed a fix; use verified knowledge and include escalation where needed.\nTicket: "+json.dumps(dict(t),ensure_ascii=False)+"\nKnowledge base: "+knowledge()
 answer,err=call_ai(prompt,"You are a cautious IT helpdesk triage agent. Return valid JSON only.")
 if answer:
  try:
   cleaned=answer.replace(chr(96)*3+"json","").replace(chr(96)*3,"").strip();d=json.loads(cleaned)
  except:d={"category":"Other","priority":"Normal","suggested_fix":answer,"owner_role":"IT Support"}
 else:d={"category":"Other","priority":"Normal","suggested_fix":"AI triage unavailable: configure OPENAI_API_KEY. Review manually and consult Fixes / Known Issues.","owner_role":"IT Support"}
 with conn() as c:c.execute("UPDATE tickets SET category=?,priority=?,suggested_fix=?,owner=CASE WHEN owner='' THEN ? ELSE owner END,updated_at=? WHERE id=?",(d.get("category","Other"),d.get("priority","Normal"),d.get("suggested_fix",""),d.get("owner_role","IT Support"),datetime.utcnow().isoformat(timespec="minutes"),id))
 log("Ticket triaged","#%s priority %s"%(id,d.get("priority","Normal")));return d
def report():
 now=datetime.utcnow()
 with conn() as c:rows=c.execute("SELECT id,title,priority,owner,created_at FROM tickets WHERE status NOT IN ('Resolved','Closed') ORDER BY created_at").fetchall()
 aging=[]
 for t in rows:
  try:days=(now-datetime.fromisoformat(t["created_at"])).days
  except:days=0
  if days>=2:aging.append("#%s %s (%sd, %s)"%(t["id"],t["title"],days,t["priority"]))
 log("Daily unresolved queue","Open: %d; 2+ day aging: %s"%(len(rows),"; ".join(aging) if aging else "none"),"Scheduled IT Support Agent")
@app.get("/")
def home():return render_template_string(HTML)
@app.get("/api/tickets")
def get_tickets():
 with conn() as c:r=c.execute("SELECT * FROM tickets ORDER BY CASE priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Normal' THEN 2 ELSE 3 END,updated_at DESC").fetchall()
 return jsonify([dict(x) for x in r])
@app.post("/api/tickets")
def new_ticket():
 d=request.get_json(force=True)
 if not d.get("title","").strip() or not d.get("description","").strip():return jsonify(error="Title and description are required"),400
 now=datetime.utcnow().isoformat(timespec="minutes")
 with conn() as c:
  cur=c.execute("INSERT INTO tickets(title,description,requester,priority,owner,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(d["title"],d["description"],d.get("requester",""),d.get("priority","Normal"),d.get("owner",""),now,now));id=cur.lastrowid
 log("Ticket created","#%d %s"%(id,d["title"]));triage(id);return jsonify(id=id),201
@app.patch("/api/tickets/<int:id>")
def patch_ticket(id):
 d=request.get_json(force=True);allow={"status","priority","owner","category","title","description"};keys=[k for k in d if k in allow]
 if not keys:return jsonify(error="No supported fields"),400
 vals=[d[k] for k in keys]+[datetime.utcnow().isoformat(timespec="minutes"),id]
 with conn() as c:c.execute("UPDATE tickets SET "+",".join(k+"=?" for k in keys)+",updated_at=? WHERE id=?",vals)
 log("Ticket updated","Ticket #"+str(id));return jsonify(ok=True)
@app.post("/api/tickets/<int:id>/triage")
def retriage(id):
 d=triage(id)
 if d is None:return jsonify(error="Ticket not found"),404
 return jsonify(d)
@app.get("/api/fixes")
def get_fixes():
 with conn() as c:r=c.execute("SELECT * FROM fixes ORDER BY verified DESC,id DESC").fetchall()
 return jsonify([dict(x) for x in r])
@app.post("/api/fixes")
def add_fix():
 d=request.get_json(force=True)
 if not all(d.get(k) for k in ("title","symptoms","solution")):return jsonify(error="Title, symptoms and solution required"),400
 with conn() as c:cur=c.execute("INSERT INTO fixes(title,symptoms,solution,verified,created_at) VALUES(?,?,?,?,?)",(d["title"],d["symptoms"],d["solution"],int(bool(d.get("verified"))),datetime.utcnow().isoformat(timespec="minutes")))
 log("Fix added",d["title"]);return jsonify(id=cur.lastrowid),201
@app.get("/api/assets")
def get_assets():
 with conn() as c:r=c.execute("SELECT * FROM assets ORDER BY name").fetchall()
 return jsonify([dict(x) for x in r])
@app.post("/api/assets")
def add_asset():
 d=request.get_json(force=True)
 if not d.get("name"):return jsonify(error="Asset name required"),400
 try:
  with conn() as c:cur=c.execute("INSERT INTO assets(name,tag,kind,assigned_to,status,notes) VALUES(?,?,?,?,?,?)",(d["name"],d.get("tag") or None,d.get("kind","Computer"),d.get("assigned_to",""),d.get("status","Active"),d.get("notes","")))
 except sqlite3.IntegrityError:return jsonify(error="Asset tag already exists"),409
 log("Asset added",d["name"]);return jsonify(id=cur.lastrowid),201
@app.get("/api/known")
def get_known():
 with conn() as c:r=c.execute("SELECT * FROM known ORDER BY active DESC,id DESC").fetchall()
 return jsonify([dict(x) for x in r])
@app.post("/api/known")
def add_known():
 d=request.get_json(force=True)
 if not d.get("title") or not d.get("details"):return jsonify(error="Title and details required"),400
 with conn() as c:cur=c.execute("INSERT INTO known(title,details,workaround) VALUES(?,?,?)",(d["title"],d["details"],d.get("workaround","")))
 log("Known issue added",d["title"]);return jsonify(id=cur.lastrowid),201
@app.get("/api/logs")
def get_logs():
 with conn() as c:r=c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 100").fetchall()
 return jsonify([dict(x) for x in r])
@app.post("/api/report")
def run_report():report();return jsonify(ok=True)
@app.get("/api/health")
def health():return jsonify(status="ok",ai_configured=bool(os.getenv("OPENAI_API_KEY")))
HTML="""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IT Support Agent</title><style>
body{margin:0;background:#0b1220;color:#eff6ff;font:15px system-ui}header{padding:22px 5%;border-bottom:1px solid #2b3a53;display:flex;justify-content:space-between}main{max-width:1250px;margin:24px auto;padding:0 18px}.grid{display:grid;grid-template-columns:360px 1fr;gap:18px}.box{background:#172236;border:1px solid #2b3a53;border-radius:14px;padding:16px;margin-bottom:16px}h1{margin:0;font-size:24px}h2{margin:0 0 12px;font-size:17px}input,select,textarea{box-sizing:border-box;width:100%;background:#0e192b;border:1px solid #2b3a53;border-radius:8px;color:#eff6ff;padding:10px;margin:5px 0 9px;font:inherit}textarea{min-height:85px}button{background:#63d4b2;color:#082018;border:0;border-radius:8px;padding:10px 13px;font-weight:700;margin:3px;cursor:pointer}.alt{background:#2a3b55;color:white}.card{border:1px solid #2b3a53;border-radius:11px;padding:12px;margin:9px 0}.muted{color:#9fb0c8;font-size:12px}.row{display:flex;gap:8px}.row>*{flex:1}.line{padding:8px 0;border-bottom:1px solid #2b3a53}@media(max-width:850px){.grid{grid-template-columns:1fr}}</style></head><body><header><div><h1>IT Support Agent</h1><span class="muted">Tickets · Assets · Fixes · Known Issues</span></div><button onclick="runReport()">Run queue report</button></header><main><div class="grid"><section>
<div class="box"><h2>New ticket</h2><input id="title" placeholder="Issue title"><textarea id="description" placeholder="Describe the problem, error and steps tried"></textarea><input id="requester" placeholder="Requester / team"><div class="row"><select id="priority"><option>Normal</option><option>Low</option><option>High</option><option>Critical</option></select><input id="owner" placeholder="Owner"></div><button onclick="createTicket()">Create + triage</button><p id="msg" class="muted"></p></div>
<div class="box"><h2>Fixes library</h2><input id="ft" placeholder="Fix title"><input id="fs" placeholder="Symptoms / keywords"><textarea id="fsol" placeholder="Solution steps"></textarea><label><input id="fv" type="checkbox" style="width:auto"> Verified</label><button onclick="saveFix()">Save fix</button><div id="fixes"></div></div>
<div class="box"><h2>Asset inventory</h2><input id="an" placeholder="Asset name"><div class="row"><input id="atag" placeholder="Asset tag"><select id="ak"><option>Computer</option><option>Printer</option><option>Network</option><option>Mobile</option><option>Software</option><option>Other</option></select></div><input id="aa" placeholder="Assigned to"><button onclick="saveAsset()">Add asset</button><div id="assets"></div></div>
<div class="box"><h2>Known issues</h2><input id="kt" placeholder="Issue title"><textarea id="kd" placeholder="Details / impact"></textarea><textarea id="kw" placeholder="Workaround"></textarea><button onclick="saveKnown()">Add issue</button><div id="known"></div></div>
</section><section><div class="box"><h2>Ticket inbox</h2><div><button class="alt" onclick="filter='All';loadTickets()">All</button><button class="alt" onclick="filter='Open';loadTickets()">Open</button><button class="alt" onclick="filter='In Progress';loadTickets()">In progress</button><button class="alt" onclick="filter='Resolved';loadTickets()">Resolved</button></div><div id="tickets"></div></div><div class="box"><h2>Agent activity</h2><div id="logs"></div></div></section></div></main>
<script>
let filter='All';
async function api(p,m='GET',d){let r=await fetch(p,{method:m,headers:{'Content-Type':'application/json'},body:d?JSON.stringify(d):undefined}),j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j}
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function createTicket(){msg.textContent='Creating and triaging…';try{await api('/api/tickets','POST',{title:title.value,description:description.value,requester:requester.value,priority:priority.value,owner:owner.value});title.value='';description.value='';msg.textContent='Ticket created; triage complete.';loadTickets()}catch(e){msg.textContent=e.message}}
async function loadTickets(){let a=await api('/api/tickets');tickets.innerHTML=a.filter(t=>filter==='All'||t.status===filter).map(t=>'<div class="card"><b>#'+t.id+' '+esc(t.title)+'</b><div class="muted">'+esc(t.priority)+' · '+esc(t.status)+' · '+esc(t.category)+' · '+esc(t.requester)+'</div><p>'+esc(t.description)+'</p><b>Suggested fix</b><p>'+esc(t.suggested_fix)+'</p><div class="row"><select id="st'+t.id+'"><option>'+esc(t.status)+'</option><option>Open</option><option>In Progress</option><option>Waiting</option><option>Resolved</option><option>Closed</option></select><input id="ow'+t.id+'" placeholder="Owner" value="'+esc(t.owner)+'"></div><button onclick="updateTicket('+t.id+')">Save status / owner</button><button class="alt" onclick="triage('+t.id+')">Re-triage</button></div>').join('')||'<p class="muted">No tickets in this view.</p>';loadLogs()}
async function updateTicket(id){await api('/api/tickets/'+id,'PATCH',{status:document.getElementById('st'+id).value,owner:document.getElementById('ow'+id).value});loadTickets()}
async function triage(id){await api('/api/tickets/'+id+'/triage','POST',{});loadTickets()}
async function saveFix(){try{await api('/api/fixes','POST',{title:ft.value,symptoms:fs.value,solution:fsol.value,verified:fv.checked});ft.value='';fs.value='';fsol.value='';loadFixes()}catch(e){alert(e.message)}}
async function loadFixes(){let a=await api('/api/fixes');fixes.innerHTML=a.map(x=>'<div class="line"><b>'+esc(x.title)+(x.verified?' ✓':'')+'</b><p>'+esc(x.symptoms)+'</p><small>'+esc(x.solution)+'</small></div>').join('')}
async function saveAsset(){try{await api('/api/assets','POST',{name:an.value,tag:atag.value,kind:ak.value,assigned_to:aa.value});an.value='';atag.value='';aa.value='';loadAssets()}catch(e){alert(e.message)}}
async function loadAssets(){let a=await api('/api/assets');assets.innerHTML=a.map(x=>'<div class="line"><b>'+esc(x.name)+'</b> <span class="muted">'+esc(x.kind)+' · '+esc(x.tag)+' · '+esc(x.assigned_to)+'</span></div>').join('')}
async function saveKnown(){try{await api('/api/known','POST',{title:kt.value,details:kd.value,workaround:kw.value});kt.value='';kd.value='';kw.value='';loadKnown()}catch(e){alert(e.message)}}
async function loadKnown(){let a=await api('/api/known');known.innerHTML=a.map(x=>'<div class="line"><b>'+esc(x.title)+'</b><p>'+esc(x.details)+'</p><small>'+esc(x.workaround)+'</small></div>').join('')}
async function loadLogs(){let a=await api('/api/logs');logs.innerHTML=a.slice(0,15).map(x=>'<div class="line"><b>'+esc(x.action)+'</b> · '+esc(x.agent)+'<br><span class="muted">'+esc(x.created_at)+' — '+esc(x.detail)+'</span></div>').join('')}
async function runReport(){await api('/api/report','POST',{});alert('Queue report logged');loadLogs()}
loadTickets();loadFixes();loadAssets();loadKnown();
</script></body></html>"""
if __name__=="__main__":
 init();sched.add_job(report,"cron",hour=17,minute=0,id="daily_report",replace_existing=True);sched.start();app.run(host="0.0.0.0",port=int(os.getenv("PORT","8080")))
