"""Tests for the new formula/QUBO API endpoints (precision presets, compare, explain)."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///_test_api.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from qguide.app.main import app  # noqa: E402

client = TestClient(app)

EXAMPLE = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
           "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
           "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def test_precision_presets_endpoint():
    r = client.get("/precision/presets")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "balanced" in data and "positive" in data["balanced"] and "penalty" in data["balanced"]
    assert len(data) >= 9


def test_design_returns_precision_and_bio_and_severity():
    """The public /design endpoint now serializes the new per-guide fields."""
    r = client.post("/design", json={"sequence": EXAMPLE, "gene_name": "T",
                                     "set_size": 3, "cell_type": "hek293"})
    assert r.status_code == 200, r.text
    g0 = r.json()["guides"][0]
    assert "precision" in g0 and 0.0 <= g0["precision"]["score"] <= 1.0
    assert g0["precision"]["components"]
    assert "bio_context" in g0
    assert g0["off_target"]["severity"] is not None


def test_optimizer_compare_endpoint():
    r = client.post("/optimizer/compare", json={
        "request": {"sequence": EXAMPLE, "set_size": 3, "optimizer_preset": "max_specificity"},
        "preset": "max_specificity"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["comparison"]["sets"]) == {
        "top_n_individual", "classical_optimized", "quantum_inspired_optimized"}
    assert "verdict" in body["comparison"]
    assert body["set_explanation"]["text"]


def test_precision_explain_endpoint():
    r = client.post("/precision/explain", json={"request": {"sequence": EXAMPLE, "set_size": 2}})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["why_high"] and e["validate"]
    assert "missing_data" in e


def test_compare_rejects_empty_sequence():
    r = client.post("/optimizer/compare", json={"request": {"sequence": "   "}})
    assert r.status_code == 400
