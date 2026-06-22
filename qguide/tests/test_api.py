"""Tests for the FastAPI auth + credits + projects + run API."""
import os

# Use an isolated SQLite DB for the API tests (reset each run, before any import
# of qguide.app.db creates the engine).
_DB = "_test_api.db"
for _ext in ("", "-wal", "-shm"):
    try:
        os.remove(_DB + _ext)
    except OSError:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from qguide.app.main import app  # noqa: E402

client = TestClient(app)

EXAMPLE = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
           "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
           "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _signup(email, name="Tester", pw="pw123456"):
    return client.post("/auth/signup", json={"name": name, "email": email, "password": pw})


def _auth(email):
    r = client.post("/auth/login", json={"email": email, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_signup_grants_bonus_and_token():
    r = _signup("a@test.com")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token"]
    assert body["account"]["credits"] == 25
    assert body["account"]["plan"] == "Free trial"


def test_duplicate_signup_blocked():
    _signup("dup@test.com")
    r = _signup("dup@test.com")
    assert r.status_code == 409


def test_login_wrong_password():
    _signup("b@test.com")
    r = client.post("/auth/login", json={"email": "b@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_auth():
    assert client.get("/me").status_code == 401
    _signup("c@test.com")
    r = client.get("/me", headers=_auth("c@test.com"))
    assert r.status_code == 200
    assert r.json()["email"] == "c@test.com"


def test_run_charges_credits_and_saves_project():
    _signup("run@test.com")
    h = _auth("run@test.com")
    r = client.post("/run", json={"request": {"sequence": EXAMPLE, "gene_name": "DEMO1",
                                              "set_size": 3}}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["balance"] == 20                       # 25 - 5
    assert len(body["response"]["guides"]) > 0
    # project persisted
    projs = client.get("/projects", headers=h).json()
    assert len(projs) == 1
    pid = projs[0]["id"]
    full = client.get(f"/projects/{pid}", headers=h)
    assert full.status_code == 200
    assert len(full.json()["response"]["guides"]) > 0


def test_run_blocks_when_out_of_credits():
    _signup("broke@test.com")
    h = _auth("broke@test.com")
    payload = {"request": {"sequence": EXAMPLE, "gene_name": "X", "set_size": 2}}
    # 25 credits / 5 per run = 5 runs, then blocked
    for _ in range(5):
        assert client.post("/run", json=payload, headers=h).status_code == 200
    blocked = client.post("/run", json=payload, headers=h)
    assert blocked.status_code == 402
    assert client.get("/me", headers=h).json()["credits"] == 0


def test_buy_credits_adds_and_upgrades_plan():
    _signup("buy@test.com")
    h = _auth("buy@test.com")
    r = client.post("/credits/buy", json={"credits": 250, "price": 39.0, "label": "Pro pack"},
                    headers=h)
    assert r.status_code == 200, r.text
    acc = r.json()
    assert acc["credits"] == 275                        # 25 + 250
    assert acc["plan"] == "Pay-as-you-go"
    assert any(t["type"] == "purchase" for t in acc["transactions"])


def test_billing_packages():
    r = client.get("/billing/packages")
    assert r.status_code == 200
    body = r.json()
    assert body["credits_per_run"] == 5
    assert len(body["packages"]) >= 3


def test_delete_project():
    _signup("del@test.com")
    h = _auth("del@test.com")
    client.post("/run", json={"request": {"sequence": EXAMPLE, "set_size": 2}}, headers=h)
    pid = client.get("/projects", headers=h).json()[0]["id"]
    assert client.delete(f"/projects/{pid}", headers=h).json()["deleted"] is True
    assert client.get("/projects", headers=h).json() == []
