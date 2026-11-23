import os,tempfile
os.environ["DATABASE_PATH"]=os.path.join(tempfile.gettempdir(),"content_studio_test_"+str(os.getpid())+".db")
import app
def setup_module():
    app.init_db()
def test_health_and_create_item():
    client=app.app.test_client()
    assert client.get("/api/health").status_code==200
    response=client.post("/api/items",json={"title":"Test idea","channel":"LinkedIn","status":"Idea","body":"Example"})
    assert response.status_code==201
    assert any(x["title"]=="Test idea" for x in client.get("/api/items").get_json())
def test_guideline_creation():
    client=app.app.test_client()
    response=client.post("/api/guidelines",json={"title":"Test voice","content":"Plain and useful"})
    assert response.status_code==201
    assert any(x["title"]=="Test voice" for x in client.get("/api/guidelines").get_json())
