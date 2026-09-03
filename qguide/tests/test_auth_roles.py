"""Auth hardening, role-based access control and privilege-escalation guards."""
import os

_DB = "_test_roles.db"
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

from fastapi.testclient import TestClient  # noqa: E402

from qguide.app import roles as roles_mod  # noqa: E402
from qguide.app.main import app  # noqa: E402

client = TestClient(app)


def _signup(email, pw="pw123456", **extra):
    body = {"name": "T", "email": email, "password": pw, "accept_terms": True}
    body.update(extra)
    return client.post("/auth/signup", json=body)


def _auth(email, pw="pw123456"):
    r = client.post("/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --------------------------------------------------------------------------- #
# Signup validation                                                            #
# --------------------------------------------------------------------------- #
def test_signup_requires_terms_acceptance():
    r = client.post("/auth/signup", json={"name": "T", "email": "noterms@test.com",
                                          "password": "pw123456"})
    assert r.status_code == 400
    assert "Terms of Service" in r.json()["detail"]


def test_signup_records_terms_version():
    _signup("terms@test.com")
    h = _auth("terms@test.com")
    acct = client.get("/me", headers=h).json()
    assert acct["terms_accepted_at"]


def test_password_policy_rejects_weak_passwords():
    for pw in ("short1", "alllettersonly", "12345678", "password1"):
        r = _signup(f"weak-{pw}@test.com", pw=pw)
        assert r.status_code == 400, f"{pw} should have been rejected"


def test_signup_accepts_optional_profile_fields():
    _signup("prof@test.com", institution="Test Institute", research_area="Gene therapy")
    acct = client.get("/me", headers=_auth("prof@test.com")).json()
    assert acct["institution"] == "Test Institute"
    assert acct["research_area"] == "Gene therapy"


# --------------------------------------------------------------------------- #
# Roles                                                                        #
# --------------------------------------------------------------------------- #
def test_new_account_is_plain_user():
    _signup("plain@test.com")
    acct = client.get("/me", headers=_auth("plain@test.com")).json()
    assert acct["role"] == roles_mod.USER
    assert acct["is_admin"] is False


def test_env_configured_admin_is_promoted():
    _signup("admin@test.com")
    acct = client.get("/me", headers=_auth("admin@test.com")).json()
    assert acct["role"] == roles_mod.ADMIN
    assert acct["is_admin"] is True


def test_user_cannot_make_themselves_admin_via_profile():
    _signup("escalate@test.com")
    h = _auth("escalate@test.com")
    # The client sends role/is_admin anyway -- the API must ignore them entirely.
    r = client.patch("/account/profile", headers=h,
                     json={"name": "Hacker", "role": "ADMIN", "is_admin": True,
                           "credits": 999999, "status": "active"})
    assert r.status_code == 200
    acct = r.json()
    assert acct["role"] == roles_mod.USER
    assert acct["is_admin"] is False
    assert acct["credits"] == 25          # unchanged signup bonus
    assert acct["name"] == "Hacker"       # the one field they may edit


def test_user_cannot_call_admin_role_endpoint():
    _signup("victim@test.com")
    h = _auth("escalate@test.com")
    r = client.post("/admin/role", headers=h,
                    json={"email": "escalate@test.com", "role": "ADMIN"})
    assert r.status_code == 403


def test_admin_can_assign_and_revoke_roles():
    _signup("researcher@test.com")
    ah = _auth("admin@test.com")
    r = client.post("/admin/role", headers=ah,
                    json={"email": "researcher@test.com", "role": "RESEARCHER"})
    assert r.status_code == 200 and r.json()["role"] == "RESEARCHER"
    acct = client.get("/me", headers=_auth("researcher@test.com")).json()
    assert acct["role"] == "RESEARCHER"
    assert "research_tools" in acct["permissions"]
    # and back down again
    r = client.post("/admin/role", headers=ah,
                    json={"email": "researcher@test.com", "role": "USER"})
    assert r.json()["role"] == "USER"


def test_unknown_role_rejected():
    ah = _auth("admin@test.com")
    r = client.post("/admin/role", headers=ah,
                    json={"email": "plain@test.com", "role": "SUPERUSER"})
    assert r.status_code == 400


def test_last_admin_cannot_demote_themselves():
    ah = _auth("admin@test.com")
    r = client.post("/admin/role", headers=ah,
                    json={"email": "admin@test.com", "role": "USER"})
    assert r.status_code == 400
    assert client.get("/me", headers=ah).json()["role"] == "ADMIN"


# --------------------------------------------------------------------------- #
# Account status                                                               #
# --------------------------------------------------------------------------- #
def test_suspended_user_cannot_sign_in_or_use_token():
    _signup("suspended@test.com")
    h = _auth("suspended@test.com")
    assert client.get("/me", headers=h).status_code == 200

    ah = _auth("admin@test.com")
    r = client.post("/admin/status", headers=ah,
                    json={"email": "suspended@test.com", "status": "suspended"})
    assert r.status_code == 200 and r.json()["status"] == "suspended"

    # existing token is rejected immediately (status is re-read per request)
    assert client.get("/me", headers=h).status_code == 403
    # and a fresh sign-in is refused
    assert client.post("/auth/login", json={"email": "suspended@test.com",
                                            "password": "pw123456"}).status_code == 403

    client.post("/admin/status", headers=ah,
                json={"email": "suspended@test.com", "status": "active"})
    assert client.get("/me", headers=h).status_code == 200


def test_admin_cannot_suspend_themselves():
    ah = _auth("admin@test.com")
    r = client.post("/admin/status", headers=ah,
                    json={"email": "admin@test.com", "status": "suspended"})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Branding + legal                                                             #
# --------------------------------------------------------------------------- #
def test_branding_endpoint_is_public_and_complete():
    b = client.get("/branding").json()
    for key in ("app_name", "app_description", "tagline", "support_email",
                "legal_company_name", "logo_mark", "terms_version"):
        assert b.get(key), f"missing branding key: {key}"


def test_legal_documents_available():
    index = client.get("/legal").json()
    slugs = {d["slug"] for d in index["documents"]}
    assert slugs == {"terms", "privacy", "disclaimer"}
    for slug in slugs:
        doc = client.get(f"/legal/{slug}").json()
        assert doc["title"] and doc["sections"]
    assert client.get("/legal/nope").status_code == 404


def test_protected_routes_require_auth():
    for path in ("/me", "/projects", "/folders"):
        assert client.get(path).status_code == 401
    assert client.post("/run", json={"request": {"sequence": "ACGT"}}).status_code in (401, 422)


# --------------------------------------------------------------------------- #
# Admin analytics                                                              #
# --------------------------------------------------------------------------- #
def test_admin_stats_activity_health_require_admin():
    h = _auth("plain@test.com")
    for path in ("/admin/stats", "/admin/activity", "/admin/health", "/admin/users"):
        assert client.get(path, headers=h).status_code == 403, path


def test_admin_stats_shape_and_privacy():
    ah = _auth("admin@test.com")
    st = client.get("/admin/stats", headers=ah).json()
    assert st["users"]["total"] >= 5
    assert "USER" in st["users_by_role"] and "ADMIN" in st["users_by_role"]
    assert len(st["weekly"]) == 12
    assert st["recent_signups"] and "email" in st["recent_signups"][0]
    # no project content ever leaves the admin endpoints
    blob = str(st) + str(client.get("/admin/activity", headers=ah).json())
    assert "sequence" not in blob.lower() and "ACGT" not in blob
    users = client.get("/admin/users", headers=ah).json()
    assert all("n_projects" in u and "response_json" not in u for u in users)
    health = client.get("/admin/health", headers=ah).json()
    assert health["database"]["ok"] and health["database"]["migration_version"] >= 2
    assert "JWT_SECRET" not in str(health) or "configured" in str(health)


# --------------------------------------------------------------------------- #
# Onboarding                                                                   #
# --------------------------------------------------------------------------- #
def test_onboarding_shown_once_then_persisted():
    _signup("tour@test.com")
    h = _auth("tour@test.com")
    me = client.get("/me", headers=h).json()
    assert me["onboarding"]["completed"] is False and me["onboarding"]["step"] == 0
    # progress is saved step by step
    r = client.patch("/account/onboarding", headers=h, json={"step": 4})
    assert r.status_code == 200 and r.json()["step"] == 4
    # finishing marks it complete with a timestamp
    r = client.patch("/account/onboarding", headers=h, json={"completed": True})
    assert r.json()["completed"] is True and r.json()["completed_at"]
    # a fresh sign-in does not show it again
    h2 = _auth("tour@test.com")
    assert client.get("/me", headers=h2).json()["onboarding"]["completed"] is True
    # replay from settings resets it
    r = client.patch("/account/onboarding", headers=h2, json={"completed": False})
    assert r.json() == {"completed": False, "step": 0, "completed_at": None}
    assert client.get("/account/onboarding").status_code == 401
