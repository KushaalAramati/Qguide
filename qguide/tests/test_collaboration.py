"""Project collaboration: memberships, server-side authorization, invitations."""
import os

_DB = "_test_collab.db"
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
os.environ["SIGNUP_RATE_LIMIT"] = "1000"   # many sign-ins from one client in this suite

from fastapi.testclient import TestClient  # noqa: E402

from qguide.app.main import app  # noqa: E402

client = TestClient(app)

EXAMPLE = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
           "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
           "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _signup(email, name="T"):
    r = client.post("/auth/signup", json={"name": name, "email": email,
                                          "password": "pw123456", "accept_terms": True})
    # 409 = already created by another test module sharing the engine (admin@)
    assert r.status_code in (200, 409), r.text


def _auth(email):
    r = client.post("/auth/login", json={"email": email, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _run(h, name="BRCA1 Knockout"):
    r = client.post("/run", headers=h, json={"request": {
        "sequence": EXAMPLE, "gene_name": name, "cas_enzyme": "SpCas9",
        "organism": "human", "desired_outcome": "knockout", "set_size": 3}})
    assert r.status_code == 200, r.text
    return r.json()


OWNER, EDITOR, VIEWER, STRANGER = ("owner@test.com", "editor@test.com",
                                   "viewer@test.com", "stranger@test.com")


def setup_module(_):
    for e, n in ((OWNER, "Kushaal"), (EDITOR, "Researcher One"),
                 (VIEWER, "Researcher Two"), (STRANGER, "Nobody"), ("admin@test.com", "Admin")):
        _signup(e, n)
    ah = _auth("admin@test.com")
    for e in (OWNER, EDITOR):
        assert client.post("/admin/credits", headers=ah, json={"email": e, "credits": 1000}).status_code == 200


def _project():
    oh = _auth(OWNER)
    run = _run(oh)
    return oh, run["project_id"], run["uid"]


def test_run_returns_global_uid_and_project_reachable_by_both_ids():
    oh, pid, uid = _project()
    assert len(uid) == 32
    a = client.get(f"/projects/{pid}", headers=oh).json()
    b = client.get(f"/projects/{uid}", headers=oh).json()
    assert a["uid"] == b["uid"] == uid
    assert a["access"]["role"] == "OWNER" and a["access"]["can_share"] is True
    assert a["members"][0]["role"] == "OWNER"


def test_unauthorized_user_cannot_open_project_url():
    oh, pid, uid = _project()
    sh = _auth(STRANGER)
    # guessing either identifier yields 404 -- existence is not revealed
    assert client.get(f"/projects/{uid}", headers=sh).status_code == 404
    assert client.get(f"/projects/{pid}", headers=sh).status_code == 404
    assert client.get(f"/projects/{uid}/members", headers=sh).status_code == 404
    assert client.patch(f"/projects/{uid}", headers=sh, json={"name": "pwned"}).status_code == 404
    assert client.delete(f"/projects/{uid}", headers=sh).status_code == 404
    assert client.get(f"/projects/{uid}", headers=oh).json()["name"] == "BRCA1 Knockout"


def test_owner_invites_editor_and_editor_can_access_and_modify():
    oh, pid, uid = _project()
    r = client.post(f"/projects/{uid}/members", headers=oh,
                    json={"email": EDITOR, "role": "EDITOR"})
    assert r.status_code == 200, r.text
    assert r.json()["member"]["name"] == "Researcher One"

    eh = _auth(EDITOR)
    p = client.get(f"/projects/{uid}", headers=eh).json()
    assert p["access"]["role"] == "EDITOR"
    assert p["access"]["can_edit"] and p["access"]["can_run"]
    assert not p["access"]["can_share"] and not p["access"]["can_delete"]
    # editor can rename and save a selected guide
    assert client.patch(f"/projects/{uid}", headers=eh, json={"name": "BRCA1 KO v2"}).status_code == 200
    gid = p["response"]["guides"][1]["guide_id"]
    assert client.patch(f"/projects/{uid}", headers=eh, json={"selected_guide": gid}).status_code == 200
    p2 = client.get(f"/projects/{uid}", headers=oh).json()
    assert p2["name"] == "BRCA1 KO v2" and p2["selected_guide"] == gid
    # ...but cannot share, delete, or organise the owner's library
    assert client.post(f"/projects/{uid}/members", headers=eh,
                       json={"email": STRANGER, "role": "VIEWER"}).status_code == 403
    assert client.delete(f"/projects/{uid}", headers=eh).status_code == 403
    assert client.patch(f"/projects/{uid}", headers=eh, json={"archived": True}).status_code == 403
    # the shared project shows up in the editor's list with their role
    mine = client.get("/projects", headers=eh).json()
    shared = [x for x in mine if x.get("shared")]
    assert shared and shared[0]["uid"] == uid and shared[0]["role"] == "EDITOR"
    assert shared[0]["owner_name"] == "Kushaal"


def test_editor_can_rerun_in_place_and_is_charged():
    oh, pid, uid = _project()
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": EDITOR, "role": "EDITOR"})
    eh = _auth(EDITOR)
    before = client.get("/me", headers=eh).json()["credits"]
    r = client.post(f"/projects/{uid}/rerun", headers=eh, json={"overrides": {"set_size": 2}})
    assert r.status_code == 200, r.text
    assert r.json()["balance"] == before - 5
    p = client.get(f"/projects/{uid}", headers=oh).json()
    assert p["response"]["request"]["set_size"] == 2
    # owner's credits untouched
    assert client.get("/me", headers=oh).json()["credits"] >= 0
    # the owner got a notification about it
    from qguide.app import store
    from qguide.app.db import session_scope
    with session_scope() as s:
        rows = s.query(store.Notification).filter_by(user_email=OWNER, type="analysis_completed").all()
        assert rows


def test_viewer_can_read_but_not_modify():
    oh, pid, uid = _project()
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": VIEWER, "role": "VIEWER"})
    vh = _auth(VIEWER)
    p = client.get(f"/projects/{uid}", headers=vh)
    assert p.status_code == 200 and p.json()["access"]["role"] == "VIEWER"
    assert p.json()["access"]["can_edit"] is False
    assert client.patch(f"/projects/{uid}", headers=vh, json={"name": "nope"}).status_code == 403
    assert client.patch(f"/projects/{uid}", headers=vh, json={"selected_guide": "x"}).status_code == 403
    assert client.post(f"/projects/{uid}/rerun", headers=vh, json={}).status_code == 403
    assert client.delete(f"/projects/{uid}", headers=vh).status_code == 403
    assert client.post(f"/projects/{uid}/members", headers=vh,
                       json={"email": STRANGER, "role": "VIEWER"}).status_code == 403
    assert client.get(f"/projects/{uid}", headers=oh).json()["name"] == "BRCA1 Knockout"
    # viewer can see who else is on the project
    m = client.get(f"/projects/{uid}/members", headers=vh).json()
    assert {x["role"] for x in m["members"]} == {"OWNER", "VIEWER"}


def test_owner_changes_and_removes_collaborators():
    oh, pid, uid = _project()
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": VIEWER, "role": "VIEWER"})
    r = client.patch(f"/projects/{uid}/members/{VIEWER}", headers=oh, json={"role": "EDITOR"})
    assert r.status_code == 200
    assert client.get(f"/projects/{uid}", headers=_auth(VIEWER)).json()["access"]["role"] == "EDITOR"
    r = client.delete(f"/projects/{uid}/members/{VIEWER}", headers=oh)
    assert r.status_code == 200
    assert client.get(f"/projects/{uid}", headers=_auth(VIEWER)).status_code == 404


def test_collaborator_can_leave_but_not_remove_others():
    oh, pid, uid = _project()
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": VIEWER, "role": "VIEWER"})
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": EDITOR, "role": "EDITOR"})
    eh = _auth(EDITOR)
    assert client.delete(f"/projects/{uid}/members/{VIEWER}", headers=eh).status_code == 403
    assert client.delete(f"/projects/{uid}/members/{OWNER}", headers=eh).status_code == 403
    assert client.delete(f"/projects/{uid}/members/{OWNER}", headers=oh).status_code == 400
    assert client.delete(f"/projects/{uid}/members/{EDITOR}", headers=eh).status_code == 200
    assert client.get(f"/projects/{uid}", headers=eh).status_code == 404


def test_invite_validation():
    oh, pid, uid = _project()
    assert client.post(f"/projects/{uid}/members", headers=oh,
                       json={"email": "ghost@test.com", "role": "VIEWER"}).status_code == 404
    assert client.post(f"/projects/{uid}/members", headers=oh,
                       json={"email": OWNER, "role": "VIEWER"}).status_code == 400
    assert client.post(f"/projects/{uid}/members", headers=oh,
                       json={"email": VIEWER, "role": "OWNER"}).status_code == 400
    r = client.get("/users/lookup", headers=oh, params={"email_q": EDITOR})
    assert r.json()["found"] and r.json()["user"]["name"] == "Researcher One"
    assert client.get("/users/lookup", headers=oh, params={"email_q": "x@y.z"}).json()["found"] is False
    assert client.get("/users/lookup", params={"email_q": EDITOR}).status_code == 401


def test_delete_project_removes_memberships():
    oh, pid, uid = _project()
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": VIEWER, "role": "VIEWER"})
    assert client.delete(f"/projects/{uid}", headers=oh).json()["deleted"] is True
    assert client.get(f"/projects/{uid}", headers=_auth(VIEWER)).status_code == 404
    assert not [x for x in client.get("/projects", headers=_auth(VIEWER)).json() if x.get("uid") == uid]


def test_projects_list_counts_collaborators():
    oh, pid, uid = _project()
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": VIEWER, "role": "VIEWER"})
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": EDITOR, "role": "EDITOR"})
    mine = [p for p in client.get("/projects", headers=oh).json() if p["uid"] == uid][0]
    assert mine["n_collaborators"] == 2 and mine["role"] == "OWNER"


def test_legacy_projects_get_uid_via_migration():
    """A project row created before collaboration existed (uid NULL) is
    backfilled and then addressable."""
    from sqlalchemy import text
    from qguide.app.db import engine
    from qguide.app import migrations
    oh = _auth(OWNER)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO projects (email, pid, name, created, elapsed, request_json, response_json, uid)"
                          " SELECT email, 'P999', 'legacy', created, elapsed, request_json, response_json, NULL"
                          " FROM projects WHERE email = :e LIMIT 1"), {"e": OWNER})
    migrations._backfill_project_uids(engine)
    meta = client.get(f"/projects/P999", headers=oh).json()
    assert meta["uid"] and len(meta["uid"]) == 32
