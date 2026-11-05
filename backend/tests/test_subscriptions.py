from datetime import date
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import initialise, make_engine
from main import create_app
from models import Subscription, SubscriptionUpdate
from service import edit_subscription, list_subscriptions, next_charge_date


def client_for(tmp_path):
    return TestClient(create_app(tmp_path / "payall.sqlite", today=lambda: date(2026, 11, 5)))


def valid_payload(**overrides):
    payload = {
        "service": "Cloud Storage",
        "category_id": 5,
        "price": 12.0,
        "currency": "CHF",
        "billing_period": "monthly",
        "start_date": "2026-01-15",
        "auto_pay": False,
        "notification_enabled": True,
    }
    payload.update(overrides)
    return payload


def test_get_seeded_subscriptions(tmp_path):
    with client_for(tmp_path) as client:
        response = client.get("/subscriptions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["subscriptions"]) == 3
    assert data["monthly_total"] == 49.68
    assert data["subscriptions"][0]["price"] == 18.9
    assert data["subscriptions"][0]["category"] == "Entertainment"


def test_list_calculates_next_charge_dates(tmp_path):
    engine = make_engine(tmp_path / "payall.sqlite")
    initialise(engine)
    with Session(engine) as session:
        result = list_subscriptions(session, date(2026, 10, 20))
    next_dates = {subscription.service: subscription.next_charge_date for subscription in result.subscriptions}
    assert next_dates["Netflix"] == date(2026, 11, 12)
    assert next_dates["Spotify"] == date(2026, 11, 3)


def test_categories_are_fixed_and_ordered(tmp_path):
    with client_for(tmp_path) as client:
        response = client.get("/categories")
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) == 9
    assert categories[0]["name"] == "Entertainment"
    assert categories[-1]["name"] == "Other"


def test_create_subscription_and_updated_total(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload())
        assert response.status_code == 201
        assert response.headers["location"] == "/subscriptions/4"
        assert client.get(response.headers["location"]).json() == response.json()
        assert client.get("/subscriptions").json()["monthly_total"] == 61.68


def test_create_custom_subscription(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post(
            "/subscriptions",
            json=valid_payload(service="Local Gym", category_id=4, is_custom=True),
        )
    assert response.status_code == 201
    assert response.json()["is_custom"] is True
    assert response.json()["category"] == "Health & Fitness"


def test_rappen_round_trip(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(price=18.90))
        assert response.json()["price"] == 18.9
        engine = client.app.state.engine
        with Session(engine) as session:
            assert session.exec(select(Subscription).where(Subscription.id == 4)).one().price_rappen == 1890


def test_rejects_price_with_more_than_two_decimals(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(price=18.999))
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"
    assert response.json()["field"] == "price"


def test_edit_subscription_updates_fields(tmp_path):
    with client_for(tmp_path) as client:
        response = client.patch("/subscriptions/1", json={"price": 19.90, "notification_enabled": True})
    assert response.status_code == 200
    assert response.json()["price"] == 19.9
    assert response.json()["notification_enabled"] is True


def test_edit_subscription_rejects_invalid_price(tmp_path):
    with client_for(tmp_path) as client:
        response = client.patch("/subscriptions/1", json={"price": 0})
    assert response.status_code == 422
    assert response.json() == {"error": "price_must_be_positive", "field": "price"}


def test_patch_rejects_is_custom(tmp_path):
    with client_for(tmp_path) as client:
        response = client.patch("/subscriptions/1", json={"is_custom": True})
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"


def test_unknown_category_is_rejected(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(category_id=999))
    assert response.status_code == 422
    assert response.json() == {"error": "category_not_found", "field": "category_id"}


def test_read_subscription(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/subscriptions/1").json()["service"] == "Netflix"
        response = client.get("/subscriptions/999")
    assert response.status_code == 404
    assert response.json() == {"error": "subscription_not_found", "field": "id"}


def test_edit_subscription_plan_change_starts_at_next_charge(tmp_path):
    engine = make_engine(tmp_path / "payall.sqlite")
    initialise(engine)
    with Session(engine) as session:
        subscription = Subscription(
            user_id=1,
            service="Monthly",
            is_custom=False,
            category_id=1,
            price_rappen=1000,
            currency="CHF",
            billing_period="monthly",
            start_date=date(2026, 1, 15),
            auto_pay=False,
            notification_enabled=False,
        )
        session.add(subscription)
        session.commit()
        subscription = edit_subscription(
            session, subscription.id, SubscriptionUpdate(billing_period="yearly"), date(2026, 3, 20)
        )
    assert subscription.start_date == date(2026, 4, 15)
    assert subscription.next_charge_date == date(2026, 4, 15)


def test_delete_subscription_removes_it_and_updates_total(tmp_path):
    with client_for(tmp_path) as client:
        assert client.delete("/subscriptions/1").status_code == 204
        subscriptions = client.get("/subscriptions").json()
    assert [item["service"] for item in subscriptions["subscriptions"]] == ["SBB Halbtax", "Spotify"]
    assert subscriptions["monthly_total"] == 30.78


def test_ids_are_not_reused_after_delete(tmp_path):
    with client_for(tmp_path) as client:
        assert client.delete("/subscriptions/3").status_code == 204
        response = client.post("/subscriptions", json=valid_payload())
    assert response.status_code == 201
    assert response.json()["id"] == 4


def test_delete_subscription_returns_not_found_for_missing_subscription(tmp_path):
    with client_for(tmp_path) as client:
        response = client.delete("/subscriptions/999")
    assert response.status_code == 404
    assert response.json() == {"error": "subscription_not_found", "field": "id"}


def test_rejects_non_positive_prices(tmp_path):
    with client_for(tmp_path) as client:
        for price in (0, -5):
            response = client.post("/subscriptions", json=valid_payload(price=price))
            assert response.status_code == 422
            assert response.json() == {"error": "price_must_be_positive", "field": "price"}


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
