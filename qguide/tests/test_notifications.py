"""Notifications: events, read state, deep links, preferences."""
import os

_DB = "_test_notif.db"
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

EXAMPLE = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
           "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
           "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")
O, C = "notif-owner@test.com", "notif-collab@test.com"


def _signup(email):
    r = client.post("/auth/signup", json={"name": "N", "email": email, "password": "pw123456", "accept_terms": True})
    assert r.status_code in (200, 409)


def _auth(email):
    r = client.post("/auth/login", json={"email": email, "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def setup_module(_):
    _signup(O); _signup(C)


def test_invite_creates_notification_with_link_and_read_flow():
    oh, ch = _auth(O), _auth(C)
    assert client.get("/notifications", headers=ch).json()["unread"] == 0
    uid = client.post("/run", headers=oh, json={"request": {"sequence": EXAMPLE, "gene_name": "N1"}}).json()["uid"]
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": C, "role": "VIEWER"})
    box = client.get("/notifications", headers=ch).json()
    assert box["unread"] == 1
    n = box["items"][0]
    assert n["type"] == "project_invite" and n["link"] == f"/project/{uid}" and n["read"] is False
    assert "N1" in n["title"]
    r = client.post(f"/notifications/{n['id']}/read", headers=ch)
    assert r.json()["unread"] == 0
    assert client.get("/notifications", headers=ch, params={"unread_only": True}).json()["items"] == []
    client.post(f"/notifications/{n['id']}/unread", headers=ch)
    assert client.get("/notifications/unread-count", headers=ch).json()["unread"] == 1
    # role change + removal notify too; mark-all clears
    client.patch(f"/projects/{uid}/members/{C}", headers=oh, json={"role": "EDITOR"})
    client.delete(f"/projects/{uid}/members/{C}", headers=oh)
    assert client.get("/notifications/unread-count", headers=ch).json()["unread"] == 3
    assert client.post("/notifications/read-all", headers=ch).json()["marked"] == 3
    assert client.get("/notifications/unread-count", headers=ch).json()["unread"] == 0


def test_notifications_are_private():
    oh, ch = _auth(O), _auth(C)
    items = client.get("/notifications", headers=ch).json()["items"]
    assert items
    nid = items[0]["id"]
    assert client.post(f"/notifications/{nid}/read", headers=oh).status_code == 404
    assert client.delete(f"/notifications/{nid}", headers=oh).status_code == 404
    assert client.delete(f"/notifications/{nid}", headers=ch).status_code == 200
    assert client.get("/notifications").status_code == 401


def test_security_and_billing_events():
    ch = _auth(C)
    before = client.get("/notifications/unread-count", headers=ch).json()["unread"]
    r = client.post("/auth/change-password", headers=ch,
                    json={"current_password": "pw123456", "new_password": "pw1234567"})
    assert r.status_code == 200
    client.post("/auth/change-password", headers=ch,
                json={"current_password": "pw1234567", "new_password": "pw123456"})
    items = client.get("/notifications", headers=ch).json()["items"]
    assert items[0]["type"] == "security" and "password" in items[0]["title"].lower()
    client.post("/credits/buy", headers=ch, json={"credits": 10, "price": 1.0, "label": "Test pack"})
    items = client.get("/notifications", headers=ch).json()["items"]
    assert items[0]["type"] == "billing" and "10 credits" in items[0]["title"]
    assert client.get("/notifications/unread-count", headers=ch).json()["unread"] == before + 3


def test_preferences_mute_a_category():
    oh, ch = _auth(O), _auth(C)
    prefs = client.get("/account/notification-preferences", headers=ch).json()
    assert prefs["preferences"]["collaboration"] is True and "collaboration" in prefs["categories"]
    r = client.patch("/account/notification-preferences", headers=ch,
                     json={"preferences": {"collaboration": False, "bogus": True}})
    assert r.json()["preferences"]["collaboration"] is False and "bogus" not in r.json()["preferences"]
    before = client.get("/notifications/unread-count", headers=ch).json()["unread"]
    uid = client.post("/run", headers=oh, json={"request": {"sequence": EXAMPLE, "gene_name": "N2"}}).json()["uid"]
    client.post(f"/projects/{uid}/members", headers=oh, json={"email": C, "role": "VIEWER"})
    assert client.get("/notifications/unread-count", headers=ch).json()["unread"] == before
    client.patch("/account/notification-preferences", headers=ch, json={"preferences": {"collaboration": True}})
