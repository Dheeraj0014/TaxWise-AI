"""Integration tests for the financial-head CRUD, dashboard and recommendations.

The load-bearing test here is `test_dashboard_matches_calculator`: the dashboard
must agree with /tax/compare to the rupee, which is what proves it is a view of
the one engine rather than a second implementation of the tax math.
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_taxify.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.application.dto.finances import DEDUCTION_SECTIONS  # noqa: E402
from app.core.database import init_db  # noqa: E402
from app.domain.services.rate_tables import load_rate_table  # noqa: E402
from app.main import app  # noqa: E402

init_db()
client = TestClient(app)

AY = 2026


def auth_headers() -> dict:
    """Register a fresh user so each test owns isolated data."""
    email = f"fin-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": "supersecret123"})
    token = client.post("/api/v1/auth/login",
                        json={"email": email, "password": "supersecret123"}
                        ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- CRUD -------------------------------------------------------------------

def test_crud_roundtrip_for_every_head():
    h = auth_headers()
    cases = [
        ("/api/v1/income",
         {"type": "salary", "gross_amount": 1800000, "tds_paid": 210000,
          "assessment_year": AY}),
        ("/api/v1/deductions",
         {"section": "80D", "claimed_amount": 25000, "assessment_year": AY}),
        ("/api/v1/investments",
         {"instrument": "ELSS", "amount": 150000, "section": "80C",
          "assessment_year": AY}),
        ("/api/v1/loans",
         {"type": "home", "principal_paid": 100000, "interest_paid": 200000,
          "section": "24b", "assessment_year": AY}),
        ("/api/v1/insurance",
         {"type": "life", "premium": 20000, "section": "80C",
          "assessment_year": AY}),
        ("/api/v1/capital-gains",
         {"asset_class": "equity", "term": "LTCG", "amount": 300000,
          "tax_section": "112A", "assessment_year": AY}),
    ]
    for path, payload in cases:
        created = client.post(path, headers=h, json=payload)
        assert created.status_code == 201, f"{path}: {created.text}"
        row_id = created.json()["id"]

        listed = client.get(path, headers=h, params={"assessment_year": AY})
        assert listed.status_code == 200
        assert any(r["id"] == row_id for r in listed.json()), path

        assert client.delete(f"{path}/{row_id}", headers=h).status_code == 204
        assert all(r["id"] != row_id
                   for r in client.get(path, headers=h).json()), path


def test_crud_requires_auth():
    assert client.get("/api/v1/investments").status_code == 403


def test_rows_are_scoped_per_user():
    owner, other = auth_headers(), auth_headers()
    row_id = client.post("/api/v1/investments", headers=owner, json={
        "instrument": "PPF", "amount": 50000, "section": "80C",
        "assessment_year": AY}).json()["id"]

    assert client.get("/api/v1/investments", headers=other).json() == []
    # A cross-user delete must 404, not 403 — never confirm the row exists.
    assert client.delete(f"/api/v1/investments/{row_id}",
                         headers=other).status_code == 404
    # ...and the owner's row survived the attempt.
    assert client.delete(f"/api/v1/investments/{row_id}",
                         headers=owner).status_code == 204


def test_unknown_section_is_rejected():
    h = auth_headers()
    r = client.post("/api/v1/deductions", headers=h, json={
        "section": "80NOPE", "claimed_amount": 1000, "assessment_year": AY})
    assert r.status_code == 422


def test_negative_amount_is_rejected():
    h = auth_headers()
    r = client.post("/api/v1/income", headers=h, json={
        "type": "salary", "gross_amount": -1, "assessment_year": AY})
    assert r.status_code == 422


def test_dto_sections_match_the_rate_table():
    """The DTO allow-list must not drift from the YAML the engine reads."""
    allowed = set(load_rate_table(AY)["regimes"]["old"]["allowed_deductions"])
    allowed.discard("std")  # engine-internal, never user-claimed
    assert allowed <= DEDUCTION_SECTIONS, allowed - DEDUCTION_SECTIONS


# --- Dashboard --------------------------------------------------------------

def _seed_full_profile(h: dict) -> None:
    client.post("/api/v1/income", headers=h, json={
        "type": "salary", "gross_amount": 1800000, "tds_paid": 210000,
        "assessment_year": AY})
    client.post("/api/v1/income", headers=h, json={
        "type": "other", "gross_amount": 25000, "assessment_year": AY})
    client.post("/api/v1/investments", headers=h, json={
        "instrument": "ELSS", "amount": 150000, "section": "80C",
        "assessment_year": AY})
    client.post("/api/v1/investments", headers=h, json={
        "instrument": "NPS", "amount": 50000, "section": "80CCD1B",
        "assessment_year": AY})
    client.post("/api/v1/insurance", headers=h, json={
        "type": "health", "premium": 25000, "section": "80D",
        "assessment_year": AY})


def test_dashboard_summary_aggregates_stored_heads():
    h = auth_headers()
    _seed_full_profile(h)

    body = client.get("/api/v1/dashboard/summary", headers=h,
                      params={"assessment_year": AY}).json()

    assert body["has_data"] is True
    assert body["income_breakdown"] == {"salary": 1800000.0, "other": 25000.0}
    assert body["deduction_breakdown"] == {
        "80C": "150000", "80CCD1B": "50000", "80D": "25000"}
    assert body["recommended_regime"] in ("old", "new")
    assert body["headline"]["tds_paid"] == "210000"


def test_dashboard_matches_calculator():
    """Stored-data dashboard and ad-hoc /tax/compare must produce identical tax."""
    h = auth_headers()
    _seed_full_profile(h)

    dash = client.get("/api/v1/dashboard/summary", headers=h,
                      params={"assessment_year": AY}).json()
    calc = client.post("/api/v1/tax/compare", json={
        "assessment_year": AY, "regime": "new",
        "income": {"salary_gross": 1800000, "other": 25000},
        "deductions": {"80C": 150000, "80CCD1B": 50000, "80D": 25000},
        "tds_paid": 210000,
    }).json()

    for regime in ("old_regime", "new_regime"):
        assert dash[regime]["total_tax"] == calc[regime]["total_tax"], regime
        assert dash[regime]["taxable_income"] == calc[regime]["taxable_income"]
    assert dash["recommended_regime"] == calc["recommended_regime"]


def test_empty_dashboard_reports_no_data():
    body = client.get("/api/v1/dashboard/summary", headers=auth_headers(),
                      params={"assessment_year": AY}).json()
    assert body["has_data"] is False
    assert body["headline"]["total_tax"] == "0"


def test_deductions_sum_across_heads_then_engine_caps_them():
    """80C from three sources sums to 220k, but the engine must cap it at 150k."""
    h = auth_headers()
    client.post("/api/v1/income", headers=h, json={
        "type": "salary", "gross_amount": 1500000, "assessment_year": AY})
    client.post("/api/v1/investments", headers=h, json={
        "instrument": "PPF", "amount": 100000, "section": "80C",
        "assessment_year": AY})
    client.post("/api/v1/insurance", headers=h, json={
        "type": "life", "premium": 70000, "section": "80C",
        "assessment_year": AY})
    client.post("/api/v1/deductions", headers=h, json={
        "section": "80C", "claimed_amount": 50000, "assessment_year": AY})

    body = client.get("/api/v1/dashboard/summary", headers=h,
                      params={"assessment_year": AY}).json()

    assert body["deduction_breakdown"]["80C"] == "220000"      # summed as claimed
    # The engine caps it and records the cap trail for audit (§5).
    applied = body["old_regime"]["breakdown"]["deductions"]["80C"]
    assert applied == "150000 (capped from 220000)"


def test_forecast_projects_growth():
    h = auth_headers()
    _seed_full_profile(h)
    body = client.get("/api/v1/dashboard/forecast", headers=h,
                      params={"assessment_year": AY, "growth_pct": 10}).json()

    assert body["base_assessment_year"] == AY
    assert body["growth_pct"] == "10"
    # More income on the same rules means more tax.
    assert float(body["projected_tax"]) > float(body["current_tax"])


def test_forecast_with_zero_growth_is_flat():
    h = auth_headers()
    _seed_full_profile(h)
    body = client.get("/api/v1/dashboard/forecast", headers=h,
                      params={"assessment_year": AY, "growth_pct": 0}).json()
    if body["same_year_rules_reused"]:
        assert body["delta"] == "0"


# --- Recommendations --------------------------------------------------------

def test_recommendation_lifecycle():
    h = auth_headers()
    client.post("/api/v1/income", headers=h, json={
        "type": "salary", "gross_amount": 1500000, "assessment_year": AY})

    gen = client.post("/api/v1/recommendations/generate", headers=h,
                      params={"assessment_year": AY})
    assert gen.status_code == 201, gen.text
    recs = gen.json()
    assert recs, "expected strategies for an undeducted 15L salary"
    assert any(r["section"] == "80C" for r in recs)
    assert all(r["status"] == "suggested" for r in recs)

    rec_id = recs[0]["id"]
    patched = client.patch(f"/api/v1/recommendations/{rec_id}", headers=h,
                           json={"status": "accepted"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "accepted"

    accepted = client.get("/api/v1/recommendations", headers=h,
                          params={"status": "accepted"}).json()
    assert [r["id"] for r in accepted] == [rec_id]


def test_regenerating_keeps_decisions_but_replaces_suggestions():
    h = auth_headers()
    client.post("/api/v1/income", headers=h, json={
        "type": "salary", "gross_amount": 1500000, "assessment_year": AY})

    first = client.post("/api/v1/recommendations/generate", headers=h,
                        params={"assessment_year": AY}).json()
    kept = first[0]["id"]
    client.patch(f"/api/v1/recommendations/{kept}", headers=h,
                 json={"status": "dismissed"})

    client.post("/api/v1/recommendations/generate", headers=h,
                params={"assessment_year": AY})
    all_ids = {r["id"] for r in client.get("/api/v1/recommendations",
                                           headers=h).json()}

    # The dismissal survived; the other stale suggestions did not.
    assert kept in all_ids
    assert not ({r["id"] for r in first[1:]} & all_ids)


def test_recommendations_are_scoped_per_user():
    owner, other = auth_headers(), auth_headers()
    client.post("/api/v1/income", headers=owner, json={
        "type": "salary", "gross_amount": 1500000, "assessment_year": AY})
    rec_id = client.post("/api/v1/recommendations/generate", headers=owner,
                         params={"assessment_year": AY}).json()[0]["id"]

    assert client.get("/api/v1/recommendations", headers=other).json() == []
    assert client.patch(f"/api/v1/recommendations/{rec_id}", headers=other,
                        json={"status": "accepted"}).status_code == 404
