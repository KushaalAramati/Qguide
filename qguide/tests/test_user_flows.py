"""End-to-end user flows from the upgrade brief, exercised through the API:

  new user      signup -> onboarding shown -> dashboard data -> create project
  returning     login -> existing projects, onboarding not shown again
  admin         login -> admin dashboard
  collaboration owner creates -> invites editor -> editor accesses + edits
  viewer        opens project, cannot modify
  unauthorised  cannot open a project URL
"""
import os

_DB = "_test_flows.db"
for _ext in ("", "-wal", "-shm"):
    try:
        os.remove(_DB + _ext)
    except OSError:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-tests"
os.environ.setdefault("ADMIN_EMAILS", "admin@test.com")
os.environ["QGUIDE_DEV_EMAIL"] = "1"
os.environ["EMAIL_BACKEND"] = "console"
os.environ["LOGIN_RATE_LIMIT"] = "1000"
os.environ["SIGNUP_RATE_LIMIT"] = "1000"

from fastapi.testclient import TestClient  # noqa: E402

from qguide.app.main import app  # noqa: E402

client = TestClient(app)
SEQ = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
       "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
       "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def signup(email, name):
    r = client.post("/auth/signup", json={"name": name, "email": email, "password": "flow1234", "accept_terms": True})
    assert r.status_code in (200, 409), r.text
    return r.json() if r.status_code == 200 else None


def login(email):
    # admin@test.com may already exist from another module (shared engine) with
    # that module's password; try both.
    for pw in ("flow1234", "pw123456"):
        r = client.post("/auth/login", json={"email": email, "password": pw})
        if r.status_code == 200:
            return r.json(), {"Authorization": f"Bearer {r.json()['token']}"}
    raise AssertionError(r.text)


def test_new_user_flow():
    res = signup("flow-new@test.com", "Flow New")
    h = {"Authorization": f"Bearer {res['token']}"}
    acct = res["account"]
    # first login -> onboarding is due
    assert acct["onboarding"]["completed"] is False
    assert acct["role"] == "USER" and acct["credits"] == 25
    # dashboard data
    assert client.get("/projects", headers=h).json() == []
    # walk the tour and finish it
    for step in range(1, 11):
        client.patch("/account/onboarding", headers=h, json={"step": step})
    assert client.patch("/account/onboarding", headers=h, json={"completed": True}).json()["completed"]
    # create a project
    r = client.post("/run", headers=h, json={"request": {"sequence": SEQ, "gene_name": "FLOW1"}})
    assert r.status_code == 200 and r.json()["balance"] == 20
    projects = client.get("/projects", headers=h).json()
    assert [p["name"] for p in projects] == ["FLOW1"]


def test_returning_user_flow():
    res, h = login("flow-new@test.com")
    assert res["account"]["onboarding"]["completed"] is True      # not shown again
    projects = client.get("/projects", headers=h).json()
    assert projects and projects[0]["name"] == "FLOW1"
    assert client.get(f"/projects/{projects[0]['id']}", headers=h).status_code == 200


def test_admin_flow():
    signup("admin@test.com", "Admin")
    res, h = login("admin@test.com")
    assert res["account"]["is_admin"] is True
    assert client.get("/admin/stats", headers=h).status_code == 200
    assert client.get("/admin/users", headers=h).status_code == 200
    assert client.get("/admin/health", headers=h).json()["database"]["ok"]
    # and a normal user is refused
    _, uh = login("flow-new@test.com")
    assert client.get("/admin/stats", headers=uh).status_code == 403


def test_collaboration_viewer_and_unauthorised_flows():
    signup("flow-editor@test.com", "Editor")
    signup("flow-viewer@test.com", "Viewer")
    signup("flow-stranger@test.com", "Stranger")
    _, oh = login("flow-new@test.com")
    _, eh = login("flow-editor@test.com")
    _, vh = login("flow-viewer@test.com")
    _, sh = login("flow-stranger@test.com")
    uid = client.post("/run", headers=oh, json={"request": {"sequence": SEQ, "gene_name": "SHARED"}}).json()["uid"]

    # owner invites editor -> editor accesses and modifies
    assert client.post(f"/projects/{uid}/members", headers=oh, json={"email": "flow-editor@test.com", "role": "EDITOR"}).status_code == 200
    p = client.get(f"/projects/{uid}", headers=eh)
    assert p.status_code == 200 and p.json()["access"]["can_edit"]
    assert client.patch(f"/projects/{uid}", headers=eh, json={"name": "SHARED v2"}).status_code == 200
    assert client.patch(f"/research/projects/{uid}/metadata", headers=eh, json={"notes": "editor note"}).status_code == 200

    # viewer can open but cannot modify
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": "flow-viewer@test.com", "role": "VIEWER"})
    p = client.get(f"/projects/{uid}", headers=vh)
    assert p.status_code == 200 and p.json()["access"]["role"] == "VIEWER" and p.json()["name"] == "SHARED v2"
    assert client.patch(f"/projects/{uid}", headers=vh, json={"name": "x"}).status_code == 403
    assert client.patch(f"/research/projects/{uid}/metadata", headers=vh, json={"notes": "x"}).status_code == 403
    assert client.post(f"/projects/{uid}/rerun", headers=vh, json={}).status_code == 403
    assert client.get(f"/research/projects/{uid}/report", headers=vh).status_code == 200   # export allowed

    # unauthorised user cannot access the project URL at all
    assert client.get(f"/projects/{uid}", headers=sh).status_code == 404
    assert client.get(f"/research/projects/{uid}/report", headers=sh).status_code == 404
    assert client.get(f"/projects/{uid}").status_code == 401

    # both collaborators got notified
    assert client.get("/notifications/unread-count", headers=eh).json()["unread"] >= 1
    assert client.get("/notifications/unread-count", headers=vh).json()["unread"] >= 1
