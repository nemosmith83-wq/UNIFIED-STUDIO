import os,tempfile
os.environ["DATABASE_PATH"]=os.path.join(tempfile.gettempdir(),"it_support_test_"+str(os.getpid())+".db")
import app
def setup_module():
    app.init()
def test_health_and_ticket_triage_without_key():
    client=app.app.test_client()
    assert client.get("/api/health").status_code==200
    response=client.post("/api/tickets",json={"title":"Cannot connect","description":"VPN disconnects","requester":"Test"})
    assert response.status_code==201
    tickets=client.get("/api/tickets").get_json()
    assert any(t["title"]=="Cannot connect" and t["suggested_fix"] and t["owner"] for t in tickets)
def test_fixes_assets_and_known_issue():
    client=app.app.test_client()
    assert client.post("/api/fixes",json={"title":"VPN fix","symptoms":"VPN disconnect","solution":"Reconnect","verified":True}).status_code==201
    assert client.post("/api/assets",json={"name":"Laptop","tag":"TEST-1"}).status_code==201
    assert client.post("/api/known",json={"title":"VPN outage","details":"Provider outage","workaround":"Use fallback"}).status_code==201
