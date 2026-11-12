from datetime import date
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import initialise, make_engine
from main import create_app
from models import Subscription, SubscriptionUpdate, UserSubscription
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


def test_openapi_documents_custom_validation_errors(tmp_path):
    with client_for(tmp_path) as client:
        openapi = client.get("/openapi.json").json()
        response = client.get("/subscriptions/abc")

    assert "HTTPValidationError" not in str(openapi)
    assert "ValidationError" not in str(openapi)
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"
    assert response.json()["field"] == "subscription_id"


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
    assert len(categories) == 11
    assert categories[0]["name"] == "Entertainment"
    assert categories[-1]["name"] == "Other"


def test_catalog_is_seeded_with_defaults(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(tmp_path) as client:
        catalog = client.get("/catalog")
        seeded_subscription = client.get("/subscriptions/1").json()
    assert catalog.status_code == 200
    catalog_items = catalog.json()
    assert len(catalog_items) == 58
    netflix = next(item for item in catalog_items if item["name"] == "Netflix")
    assert netflix == {
        "id": 1,
        "name": "Netflix",
        "category_id": 1,
        "category": "Entertainment",
        "default_price": 18.9,
        "billing_period": "monthly",
    }
    assert seeded_subscription["next_charge_date"] == "2026-11-12"
    assert seeded_subscription["payment_status"] == "paid"
    assert seeded_subscription["status"] == "active"
    engine = make_engine(database_file)
    with Session(engine) as session:
        user_subscription = session.exec(
            select(UserSubscription).where(UserSubscription.id == 1)
        ).one()
        assert not hasattr(user_subscription, "next_charge_date")
        assert not hasattr(user_subscription, "payment_status")
        assert not hasattr(user_subscription, "status")
        catalog_subscription = session.get(Subscription, 1)
        catalog_subscription.name = "Preserved catalog edit"
        session.add(catalog_subscription)
        session.commit()
    initialise(engine)
    with Session(engine) as session:
        assert session.exec(select(Subscription)).all()[0].name == "Preserved catalog edit"


def test_create_subscription_and_updated_total(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post(
            "/subscriptions",
            json={"subscription_id": 1, "start_date": "2026-01-15", "auto_pay": False},
        )
        assert response.status_code == 201
        assert response.headers["location"] == "/subscriptions/4"
        assert client.get(response.headers["location"]).json() == response.json()
        assert client.get("/subscriptions").json()["monthly_total"] == 68.58
        assert len(client.get("/catalog").json()) == 58


def test_create_catalog_subscription_uses_custom_price(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post(
            "/subscriptions",
            json={
                "subscription_id": 1,
                "price": 25.0,
                "billing_period": "yearly",
                "start_date": "2026-01-15",
                "auto_pay": False,
            },
        )

    assert response.status_code == 201
    assert response.json()["price"] == 25.0
    assert response.json()["billing_period"] == "yearly"
    with Session(client.app.state.engine) as session:
        user_subscription = session.exec(
            select(UserSubscription).where(UserSubscription.id == response.json()["id"])
        ).one()
        assert user_subscription.price_rappen == 2500
        assert user_subscription.billing_period == "yearly"


def test_create_subscription_accepts_usd_currency(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post(
            "/subscriptions",
            json=valid_payload(currency="USD"),
        )

    assert response.status_code == 201
    assert response.json()["currency"] == "USD"


def test_create_custom_subscription(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post(
            "/subscriptions",
            json=valid_payload(service="Local Gym", category_id=4),
        )
    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "Health & Fitness"
    assert body["catalog_id"] is None
    assert body["is_custom"] is True
    catalog_items = client.get("/catalog").json()
    assert len(catalog_items) == 58
    assert not any(item["name"] == "Local Gym" for item in catalog_items)
    with Session(client.app.state.engine) as session:
        user_subscription = session.exec(
            select(UserSubscription).where(UserSubscription.id == body["id"])
        ).one()
        assert len(session.exec(select(Subscription)).all()) == 58


def test_rappen_round_trip(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(price=18.90))
        assert response.json()["price"] == 18.9
        engine = client.app.state.engine
        with Session(engine) as session:
            assert session.exec(select(UserSubscription).where(UserSubscription.id == 4)).one().price_rappen == 1890


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
    assert response.json()["error"] == "price_must_be_positive"
    assert response.json()["field"] == "price"
    assert response.json()["message"]


def test_patch_rejects_is_custom(tmp_path):
    with client_for(tmp_path) as client:
        response = client.patch("/subscriptions/1", json={"is_custom": True})
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_input"


def test_unknown_category_is_rejected(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(category_id=999))
    assert response.status_code == 422
    assert response.json()["error"] == "category_not_found"
    assert response.json()["field"] == "category_id"
    assert response.json()["message"]


def test_read_subscription(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/subscriptions/1").json()["service"] == "Netflix"
        response = client.get("/subscriptions/999")
    assert response.status_code == 404
    assert response.json()["error"] == "subscription_not_found"
    assert response.json()["field"] == "id"
    assert response.json()["message"]


def test_edit_subscription_plan_change_starts_at_next_charge(tmp_path):
    engine = make_engine(tmp_path / "payall.sqlite")
    initialise(engine)
    with Session(engine) as session:
        details = Subscription(
            name="Monthly",
            category_id=1,
            default_price_rappen=1000,
            billing_period="monthly",
        )
        session.add(details)
        session.flush()
        subscription = UserSubscription(
            user_id=1,
            service="Monthly",
            category_id=1,
            subscription_id=details.id,
            price_rappen=1000,
            currency="CHF",
            billing_period="monthly",
            start_date=date(2026, 1, 15),
            tracked_since=date(2026, 3, 20),
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
    assert response.json()["error"] == "subscription_not_found"
    assert response.json()["field"] == "id"
    assert response.json()["message"]


def test_rejects_non_positive_prices(tmp_path):
    with client_for(tmp_path) as client:
        for price in (0, -5):
            response = client.post("/subscriptions", json=valid_payload(price=price))
            assert response.status_code == 422
            assert response.json()["error"] == "price_must_be_positive"
            assert response.json()["field"] == "price"
            assert response.json()["message"]


def test_rejects_blank_service(tmp_path):
    with client_for(tmp_path) as client:
        response = client.post("/subscriptions", json=valid_payload(service="   "))
    assert response.status_code == 422
    assert response.json()["error"] == "service_name_required"
    assert response.json()["field"] == "service"
    assert response.json()["message"]


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
