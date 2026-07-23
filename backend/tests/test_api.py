"""API integration tests (§4). Uses an in-memory SQLite via the real app."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_taxify.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_calculate_new_regime():
    r = client.post("/api/v1/tax/calculate", json={
        "assessment_year": 2026, "regime": "new",
        "income": {"salary_gross": 1275000},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["taxable_income"] == "1200000"
    assert body["total_tax"] == "0"


def test_compare_returns_recommendation():
    r = client.post("/api/v1/tax/compare", json={
        "assessment_year": 2026, "regime": "new",
        "income": {"salary_gross": 1800000, "other": 25000},
        "deductions": {"80C": 150000, "80CCD1B": 50000, "80D": 25000},
        "tds_paid": 210000,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["recommended_regime"] in ("old", "new")
    assert "old_regime" in body and "new_regime" in body


def test_auth_flow_and_scoped_history():
    email = "flow@example.com"
    reg = client.post("/api/v1/auth/register",
                      json={"email": email, "password": "supersecret123"})
    assert reg.status_code in (201, 409)
    login = client.post("/api/v1/auth/login",
                        json={"email": email, "password": "supersecret123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=h)
    assert me.json()["email"] == email

    save = client.post("/api/v1/tax/save", headers=h, json={
        "assessment_year": 2026, "regime": "new",
        "income": {"salary_gross": 1275000},
    })
    assert save.status_code == 200
    hist = client.get("/api/v1/tax/computations", headers=h)
    assert hist.status_code == 200
    assert len(hist.json()) >= 1


def test_history_requires_auth():
    assert client.get("/api/v1/tax/computations").status_code == 403


def test_optimizer_recommends_for_old_regime():
    r = client.post("/api/v1/optimizer/recommend", json={
        "assessment_year": 2026, "regime": "old",
        "income": {"salary_gross": 1500000},
        "deductions": {},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["total_potential_saving"] > 0
    assert any(rec["section"] == "80C" for rec in body["recommendations"])
