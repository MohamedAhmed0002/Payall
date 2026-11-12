from datetime import date
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app
from models import UserSubscription


TODAY = date(2026, 11, 5)


def client_for(database_file: Path) -> TestClient:
    return TestClient(create_app(database_file, today=lambda: TODAY))


def custom_payload(**overrides):
    payload = {
        "service": "Local Gym",
        "category_id": 4,
        "price": 60,
        "billing_period": "monthly",
        "start_date": "2026-01-15",
        "auto_pay": False,
    }
    payload.update(overrides)
    return payload


def test_catalog_subscription_uses_catalog_defaults(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        response = client.post(
            "/subscriptions",
            json={"subscription_id": 1, "start_date": "2026-01-15", "auto_pay": False},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["service"] == "Netflix"
    assert body["category"] == "Entertainment"
    assert body["price"] == 18.9
    assert body["billing_period"] == "monthly"
    assert body["is_custom"] is False


def test_catalog_subscription_keeps_user_price_without_changing_catalog(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        response = client.post(
            "/subscriptions",
            json={
                "subscription_id": 1,
                "price": 24.90,
                "start_date": "2026-01-15",
                "auto_pay": False,
            },
        )
        netflix = next(item for item in client.get("/catalog").json() if item["name"] == "Netflix")

    assert response.status_code == 201
    assert response.json()["price"] == 24.9
    assert netflix["default_price"] == 18.9


def test_custom_subscription_requires_price_billing_period_and_service(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        missing_price = client.post(
            "/subscriptions", json=custom_payload(price=None)
        )
        missing_billing_period = client.post(
            "/subscriptions", json=custom_payload(billing_period=None)
        )
        missing_service = client.post(
            "/subscriptions", json=custom_payload(service=None)
        )

    assert missing_price.json() == {"error": "price_required", "field": "price"}
    assert missing_billing_period.json() == {
        "error": "billing_period_required",
        "field": "billing_period",
    }
    assert missing_service.json() == {
        "error": "service_name_required",
        "field": "service",
    }
    assert missing_price.status_code == missing_billing_period.status_code == 422
    assert missing_service.status_code == 422


def test_patching_service_does_not_change_catalog(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        response = client.patch("/subscriptions/1", json={"service": "Netflix family"})
        catalog_names = [item["name"] for item in client.get("/catalog").json()]

    assert response.status_code == 200
    assert response.json()["service"] == "Netflix family"
    assert "Netflix" in catalog_names
    assert "Netflix family" not in catalog_names


def test_unknown_catalog_subscription_id_is_invalid_input(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        response = client.post(
            "/subscriptions",
            json={"subscription_id": 999, "start_date": "2026-01-15", "auto_pay": False},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": "catalog_item_not_found",
        "field": "subscription_id",
    }


def test_listing_does_not_change_user_subscription_rows(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(database_file) as client:
        engine = client.app.state.engine
        with Session(engine) as session:
            before = [
                row.model_dump()
                for row in session.exec(
                    select(UserSubscription).order_by(UserSubscription.id)
                ).all()
            ]

        assert client.get("/subscriptions").status_code == 200
        assert client.get("/subscriptions").status_code == 200

        with Session(engine) as session:
            after = [
                row.model_dump()
                for row in session.exec(
                    select(UserSubscription).order_by(UserSubscription.id)
                ).all()
            ]

    assert after == before


def test_seed_monthly_total_is_unchanged(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        response = client.get("/subscriptions")

    assert response.status_code == 200
    assert response.json()["monthly_total"] == 49.68
