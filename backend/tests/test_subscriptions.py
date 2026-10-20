from datetime import date
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app
from service import next_charge_date


def client_for(tmp_path):
    return TestClient(create_app(tmp_path / "payall.sqlite"))


def valid_payload(**overrides):
    payload = {
        "service": "Cloud Storage",
        "category": "Tools",
        "price": 12.0,
        "currency": "CHF",
        "billing_period": "monthly",
        "start_date": "2026-01-15",
        "notification_enabled": True,
    }
    payload.update(overrides)
    return payload


def test_get_seeded_subscriptions(tmp_path):
    with client_for(tmp_path) as client:
        response = client.get("/subscriptions")
    assert response.status_code == 200
    assert len(response.json()["subscriptions"]) == 3
    assert response.json()["monthly_total"] == 49.68


def test_create_subscription_and_updated_total(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload())
        assert response.status_code == 201
        assert response.headers["location"] == "/subscriptions/4"
        assert response.json()["payment_status"] == "pending"
        assert response.json()["service"] == "Cloud Storage"
        assert client.get("/subscriptions").json()["monthly_total"] == 61.68


def test_create_custom_subscription(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post(
            "/subscriptions",
            json=valid_payload(service="Local Gym", category="Health", is_custom=True),
        )
    assert response.status_code == 201
    assert response.json()["is_custom"] is True


def test_rejects_non_positive_prices(tmp_path):
    with client_for(tmp_path) as client:
        for price in (0, -5):
            response = client.post("/subscriptions", json=valid_payload(price=price))
            assert response.status_code == 422
            assert response.json() == {
                "error": "price_must_be_positive",
                "field": "price",
            }


def test_rejects_blank_service(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(service="   "))
    assert response.status_code == 422
    assert response.json() == {"error": "service_name_required", "field": "service"}


def test_rejects_invalid_billing_period(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(billing_period="daily"))
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"
    assert response.json()["field"] == "billing_period"


def test_rejects_unknown_fields(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(extra="no"))
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"


def test_data_survives_restart(tmp_path):
    with client_for(tmp_path) as client:
        assert client.post("/subscriptions", json=valid_payload()).status_code == 201
    with client_for(tmp_path) as client:
        services = [item["service"] for item in client.get("/subscriptions").json()["subscriptions"]]
    assert "Cloud Storage" in services


def test_next_charge_date():
    assert next_charge_date(date(2026, 1, 31), "monthly", date(2026, 2, 10)) == date(2026, 2, 28)
    assert next_charge_date(date(2026, 2, 1), "yearly", date(2026, 10, 20)) == date(2027, 2, 1)
    assert next_charge_date(date(2026, 1, 1), "weekly", date(2026, 1, 15)) == date(2026, 1, 15)
    assert next_charge_date(date(2026, 12, 1), "monthly", date(2026, 10, 20)) == date(2026, 12, 1)
