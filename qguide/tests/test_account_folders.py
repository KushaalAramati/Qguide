"""Tests for password change/reset, profile, and folder/project organisation."""
import os

_DB = "_test_acct.db"
for _ext in ("", "-wal", "-shm"):
    try:
        os.remove(_DB + _ext)
    except OSError:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ.setdefault("ADMIN_EMAILS", "admin@test.com")  # keep order-independent with test_api
os.environ["QGUIDE_DEV_EMAIL"] = "1"   # no SMTP backend in tests -> token returned inline
os.environ["EMAIL_BACKEND"] = "console"

from fastapi.testclient import TestClient  # noqa: E402
from qguide.app.main import app  # noqa: E402

client = TestClient(app)


def _signup(email, pw="pw123456"):
    return client.post("/auth/signup", json={"name": "T", "email": email,
                                             "password": pw, "accept_terms": True})


def _auth(email, pw="pw123456"):
    r = client.post("/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_change_password_flow():
    _signup("cp@test.com")
    h = _auth("cp@test.com")
    # wrong current password rejected
    r = client.post("/auth/change-password", headers=h,
                    json={"current_password": "wrong", "new_password": "newpw123"})
    assert r.status_code == 401
    # correct change succeeds, and the new password works for login
    r = client.post("/auth/change-password", headers=h,
                    json={"current_password": "pw123456", "new_password": "newpw123"})
    assert r.status_code == 200, r.text
    assert client.post("/auth/login", json={"email": "cp@test.com", "password": "newpw123"}).status_code == 200
    assert client.post("/auth/login", json={"email": "cp@test.com", "password": "pw123456"}).status_code == 401


def test_forgot_and_reset_password_dev_mode():
    _signup("fp@test.com")
    r = client.post("/auth/forgot-password", json={"email": "fp@test.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["dev_mode"] is True and body["reset_token"]           # dev mode returns the token
    tok = body["reset_token"]
    r = client.post("/auth/reset-password", json={"token": tok, "new_password": "reset1234"})
    assert r.status_code == 200 and r.json()["token"]
    assert client.post("/auth/login", json={"email": "fp@test.com", "password": "reset1234"}).status_code == 200
    # a bogus token is rejected
    assert client.post("/auth/reset-password", json={"token": "nope", "new_password": "x1234567"}).status_code == 400


def test_forgot_unknown_email_does_not_leak():
    r = client.post("/auth/forgot-password", json={"email": "ghost@test.com"})
    assert r.status_code == 200 and r.json()["reset_token"] is None    # no token, but still 200


def test_profile_update():
    _signup("pr@test.com")
    h = _auth("pr@test.com")
    r = client.patch("/account/profile", headers=h, json={"name": "New Name"})
    assert r.status_code == 200 and r.json()["name"] == "New Name"


def test_folders_crud_and_project_move():
    _signup("fo@test.com")
    h = _auth("fo@test.com")
    # create a folder + subfolder
    f1 = client.post("/folders", headers=h, json={"name": "Screens"}).json()
    assert f1["id"].startswith("F")
    f2 = client.post("/folders", headers=h, json={"name": "Round 1", "parent_id": f1["id"]}).json()
    folders = client.get("/folders", headers=h).json()
    assert len(folders) == 2 and any(f["parent_id"] == f1["id"] for f in folders)
    # rename
    assert client.patch(f"/folders/{f1['id']}", headers=h, json={"name": "Libraries"}).status_code == 200
    assert any(f["name"] == "Libraries" for f in client.get("/folders", headers=h).json())


def test_project_patch_move_rename_archive(monkeypatch):
    _signup("pp@test.com")
    h = _auth("pp@test.com")
    # seed a project directly through the store (avoid a full design run here)
    from qguide.app import store
    from qguide.app.schemas import DesignRequest
    from qguide.core import pipeline
    req = DesignRequest(sequence="ACGT" * 25 + "TGG" + "ACGT" * 5, gene_name="g", max_guides=6, set_size=2)
    resp = pipeline.run_design(req)
    pid = store.next_pid("pp@test.com")
    store.save_project("pp@test.com", {"id": pid, "name": "g", "created": "now", "elapsed": 0.1,
                                       "selected_guide": None, "request": req, "response": resp})
    fol = client.post("/folders", headers=h, json={"name": "Box"}).json()
    # move + rename + archive via one PATCH each
    assert client.patch(f"/projects/{pid}", headers=h, json={"folder_id": fol["id"]}).status_code == 200
    assert client.patch(f"/projects/{pid}", headers=h, json={"name": "renamed"}).status_code == 200
    assert client.patch(f"/projects/{pid}", headers=h, json={"archived": True}).status_code == 200
    metas = client.get("/projects", headers=h).json()
    m = [x for x in metas if x["id"] == pid][0]
    assert m["folder_id"] == fol["id"] and m["name"] == "renamed" and m["archived"] is True
