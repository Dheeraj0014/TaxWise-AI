"""PDF export of a saved tax computation (§4 reports)."""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_taxify.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
client = TestClient(app)


def _auth() -> dict:
    email = f"pdf-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": "supersecret123"})
    token = client.post("/api/v1/auth/login",
                        json={"email": email, "password": "supersecret123"}
                        ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_pdf_download_of_saved_computation():
    h = _auth()
    saved = client.post("/api/v1/tax/save", headers=h, json={
        "assessment_year": 2026, "regime": "new",
        "income": {"salary_gross": 1800000, "other": 25000},
        "deductions": {"80C": 150000}, "tds_paid": 210000,
    })
    assert saved.status_code == 200
    cid = saved.json()["id"]

    r = client.get(f"/api/v1/tax/computations/{cid}/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"          # a real PDF, not an error page
    assert len(r.content) > 800               # actually has content


def test_pdf_404_for_unknown_id():
    r = client.get("/api/v1/tax/computations/does-not-exist/pdf", headers=_auth())
    assert r.status_code == 404


def test_pdf_is_scoped_to_owner():
    """User B cannot download user A's computation."""
    ha = _auth()
    cid = client.post("/api/v1/tax/save", headers=ha, json={
        "assessment_year": 2026, "regime": "old",
        "income": {"salary_gross": 1200000}, "tds_paid": 0,
    }).json()["id"]
    r = client.get(f"/api/v1/tax/computations/{cid}/pdf", headers=_auth())
    assert r.status_code == 404
