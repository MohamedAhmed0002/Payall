from datetime import date
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app


TODAY = date(2026, 11, 5)


def client_for(database_file: Path, current_date: date = TODAY) -> TestClient:
    return TestClient(create_app(database_file, today=lambda: current_date))


def manual_payload(start_date: str = "2026-01-01", **overrides):
    payload = {
        "service": "Manual Plan",
        "category_id": 1,
        "price": 10,
        "currency": "CHF",
        "billing_period": "monthly",
        "start_date": start_date,
        "auto_pay": False,
        "notification_enabled": True,
    }
    payload.update(overrides)
    return payload


def test_period_before_tracking_is_assumed_paid(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(database_file) as client:
        created = client.post("/subscriptions", json=manual_payload()).json()
        assert created["payment_status"] == "paid"
        assert created["next_charge_date"] == "2026-12-01"
        assert not [
            item for item in client.get("/history?type=payment").json()["items"]
            if item["service"] == "Manual Plan"
        ]
        assert not [
            item for item in client.get("/notifications").json()["items"]
            if item["service"] == "Manual Plan"
        ]
        assert client.post(f"/subscriptions/{created['id']}/payments").json() == {
            "error": "already_paid",
            "field": "id",
        }

    with client_for(database_file, date(2026, 12, 1)) as client:
        assert client.get(f"/subscriptions/{created['id']}").json()["payment_status"] == "pending"
        payment = client.post(f"/subscriptions/{created['id']}/payments")
        assert payment.status_code == 201
        assert payment.json()["period_start"] == "2026-12-01"


def test_autopay_starts_tracking_on_creation(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(database_file) as client:
        created = client.post(
            "/subscriptions",
            json=manual_payload(auto_pay=True, service="Auto Plan"),
        ).json()
        assert created["payment_status"] == "paid"
        assert not [
            item for item in client.get("/history?type=payment").json()["items"]
            if item["service"] == "Auto Plan"
        ]

    with client_for(database_file, date(2026, 12, 1)) as client:
        payments = [
            item for item in client.get("/history?type=payment").json()["items"]
            if item["service"] == "Auto Plan"
        ]
        assert len(payments) == 1
        assert payments[0]["date"] == "2026-12-01"


def test_seed_history_and_notifications_exclude_paid_and_out_of_window(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        payments = client.get("/history?type=payment").json()["items"]
        assert len([item for item in payments if item["service"] == "Netflix"]) == 14
        assert len([item for item in payments if item["service"] == "Spotify"]) == 14
        assert not [item for item in payments if item["service"] == "SBB Halbtax"]
        notifications = client.get("/notifications").json()
        assert notifications == {"count": 0, "message": None, "items": []}


def test_search_percent_is_literal_and_sort_validation_remains(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        assert client.get("/subscriptions?search=%25").json()["subscriptions"] == []
        for query, field in (
            ("/subscriptions?sort=foo", "sort"),
            ("/subscriptions?order=up", "order"),
        ):
            response = client.get(query)
            assert response.status_code == 422
            body = response.json()
            assert body["error"] == "invalid_input"
            assert body["field"] == field
            assert body["message"]


def test_post_input_limits(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        assert client.post(
            "/subscriptions",
            json=manual_payload(service="x" * 101),
        ).json() == {"error": "service_name_too_long", "field": "service"}
        assert client.post(
            "/subscriptions",
            json=manual_payload(price=100000.01),
        ).json() == {"error": "price_too_high", "field": "price"}
        assert client.post(
            "/subscriptions",
            json=manual_payload(start_date="1999-12-31"),
        ).json() == {"error": "start_date_out_of_range", "field": "start_date"}
        assert client.post(
            "/subscriptions",
            json=manual_payload(start_date="2027-11-06"),
        ).json() == {"error": "start_date_out_of_range", "field": "start_date"}


def test_patch_input_limits(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        for field, value, error in (
            ("service", "x" * 101, "service_name_too_long"),
            ("price", 100000.01, "price_too_high"),
            ("start_date", "1999-12-31", "start_date_out_of_range"),
            ("start_date", "2027-11-06", "start_date_out_of_range"),
        ):
            assert client.patch("/subscriptions/2", json={field: value}).json() == {
                "error": error,
                "field": field,
            }
