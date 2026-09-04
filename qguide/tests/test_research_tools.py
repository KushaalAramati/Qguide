"""Research tools: metadata, templates, batch runs, comparison, history, reports."""
import os

_DB = "_test_research.db"
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
EXAMPLE2 = EXAMPLE[30:] + EXAMPLE[:30]

R, V, ADMIN = "res@test.com", "view@test.com", "admin@test.com"


def _signup(email, name="T"):
    r = client.post("/auth/signup", json={"name": name, "email": email,
                                          "password": "pw123456", "accept_terms": True})
    assert r.status_code in (200, 409), r.text


def _auth(email):
    r = client.post("/auth/login", json={"email": email, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def setup_module(_):
    for e in (R, V, ADMIN):
        _signup(e)
    ah = _auth(ADMIN)
    client.post("/admin/credits", headers=ah, json={"email": R, "credits": 1000})


def _run(h, name="GENE1", seq=EXAMPLE):
    r = client.post("/run", headers=h, json={"request": {"sequence": seq, "gene_name": name,
                                                          "cas_enzyme": "SpCas9", "set_size": 3}})
    assert r.status_code == 200, r.text
    return r.json()


def test_metadata_roundtrip_and_permissions():
    h = _auth(R)
    uid = _run(h)["uid"]
    r = client.patch(f"/research/projects/{uid}/metadata", headers=h, json={
        "experiment_name": "BRCA1 KO pilot", "cell_line": "HEK293T", "target_gene": "BRCA1",
        "experiment_type": "knockout", "notes": "First pass.", "tags": ["pilot", "brca1", "pilot"],
        "citations": [{"label": "Doench 2016", "doi": "10.1038/nbt.3437"}]})
    assert r.status_code == 200, r.text
    md = r.json()["metadata"]
    assert md["tags"] == ["brca1", "pilot"] and md["updated_by"] == R
    assert md["citations"][0]["doi"] == "10.1038/nbt.3437"
    # viewer can read, not write
    client.post(f"/projects/{uid}/members", headers=h, json={"email": V, "role": "VIEWER"})
    vh = _auth(V)
    assert client.get(f"/research/projects/{uid}/metadata", headers=vh).json()["metadata"]["cell_line"] == "HEK293T"
    assert client.patch(f"/research/projects/{uid}/metadata", headers=vh, json={"notes": "x"}).status_code == 403
    assert client.patch(f"/research/projects/{uid}/metadata", headers=h,
                        json={"experiment_type": "bogus"}).status_code == 400
    assert "pilot" in client.get("/research/tags", headers=h).json()["tags"]


def test_templates_crud_and_validation():
    h = _auth(R)
    r = client.post("/research/templates", headers=h, json={
        "name": "Therapeutic-grade SpCas9", "description": "low risk",
        "params": {"cas_enzyme": "SpCas9", "risk_tolerance": "low", "set_size": 4,
                   "sequence": "SHOULD_BE_DROPPED", "organism": "human"}})
    assert r.status_code == 200, r.text
    t = r.json()
    assert "sequence" not in t["params"] and t["params"]["set_size"] == 4
    assert client.post("/research/templates", headers=h, json={
        "name": "bad", "params": {"set_size": "not-an-int"}}).status_code == 400
    r = client.patch(f"/research/templates/{t['id']}", headers=h, json={"name": "Renamed"})
    assert r.json()["name"] == "Renamed"
    assert [x["id"] for x in client.get("/research/templates", headers=h).json()["templates"]] == [t["id"]]
    # not visible to / editable by another user
    vh = _auth(V)
    assert client.get("/research/templates", headers=vh).json()["templates"] == []
    assert client.delete(f"/research/templates/{t['id']}", headers=vh).status_code == 404
    assert client.delete(f"/research/templates/{t['id']}", headers=h).status_code == 200


def test_batch_requires_researcher_role_and_runs_each_target():
    h = _auth(R)
    body = {"targets": [{"name": "TP53", "sequence": EXAMPLE}, {"name": "KRAS", "sequence": EXAMPLE2}],
            "params": {"set_size": 2}, "folder_name": "Batch 1", "tags": ["batch"]}
    assert client.get("/research/batch/limits", headers=h).json()["allowed"] is False
    assert client.post("/research/batch", headers=h, json=body).status_code == 403
    client.post("/admin/role", headers=_auth(ADMIN), json={"email": R, "role": "RESEARCHER"})
    assert client.get("/research/batch/limits", headers=h).json()["allowed"] is True
    before = client.get("/me", headers=h).json()["credits"]
    r = client.post("/research/batch", headers=h, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] == 2 and out["failed"] == 0 and out["folder_id"]
    assert out["balance"] == before - 10
    mine = client.get("/projects", headers=h).json()
    made = [p for p in mine if p["name"] in ("TP53", "KRAS")]
    assert len(made) == 2 and all(p["folder_id"] == out["folder_id"] for p in made)
    md = client.get(f"/research/projects/{out['results'][0]['uid']}/metadata", headers=h).json()["metadata"]
    assert md["target_gene"] == "TP53" and md["tags"] == ["batch"]
    # too many targets is rejected by validation
    big = {"targets": [{"name": f"g{i}", "sequence": EXAMPLE} for i in range(11)]}
    assert client.post("/research/batch", headers=h, json=big).status_code == 422


def test_compare_and_history_and_report():
    h = _auth(R)
    a = _run(h, "A")["uid"]
    b = _run(h, "B", EXAMPLE2)["uid"]
    r = client.post("/research/compare", headers=h, json={"project_ids": [a, b]})
    assert r.status_code == 200, r.text
    cmp_ = r.json()
    assert len(cmp_["projects"]) == 2
    assert cmp_["projects"][0]["stats"]["n_guides"] > 0 and cmp_["projects"][0]["top_guides"]
    # cannot compare against a project you cannot access
    vh = _auth(V)
    assert client.post("/research/compare", headers=vh, json={"project_ids": [a, b]}).status_code == 404
    hist = client.get("/research/history", headers=h).json()
    assert hist["events"] and hist["events"][0]["type"] == "usage" and hist["projects"]
    rep = client.get(f"/research/projects/{a}/report", headers=h).json()
    assert rep["report"]["candidate_guides"] and rep["reproducibility"]["request"]["gene_name"] == "A"
    assert "research use only" in rep["reproducibility"]["disclaimer"]
    md = client.get(f"/research/projects/{a}/report", headers=h, params={"fmt": "md"})
    assert md.status_code == 200 and md.text.startswith("# ") and "## Reproducibility" in md.text
    assert client.get(f"/research/projects/{a}/report", headers=vh).status_code == 404
