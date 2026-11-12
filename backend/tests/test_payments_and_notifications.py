from datetime import date
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app


TODAY = date(2026, 11, 5)


def client_for(database_file: Path, current_date: date = TODAY) -> TestClient:
    return TestClient(create_app(database_file, today=lambda: current_date))


def test_seed_payments_status_and_history(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        history = client.get("/history?type=payment").json()["items"]
        assert len(history) == 28
        assert {item["method"] for item in history if item["service"] == "Netflix"} == {"auto"}
        assert {item["method"] for item in history if item["service"] == "Spotify"} == {"auto"}
        assert not [item for item in history if item["service"] == "SBB Halbtax"]
        result = client.get("/subscriptions").json()
        assert {item["service"]: item["payment_status"] for item in result["subscriptions"]} == {
            "Netflix": "paid",
            "Spotify": "paid",
            "SBB Halbtax": "pending",
        }
        assert result["monthly_total"] == 49.68
        assert result["cancelled_excluded"] == 0


def test_repeated_listing_does_not_duplicate_payments(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        client.get("/subscriptions")
        client.get("/subscriptions")
        assert len(client.get("/history?type=payment").json()["items"]) == 28


def test_manual_payment_and_autopay_errors(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        response = client.post("/subscriptions/2/payments")
        assert response.status_code == 201
        assert response.json() == {
            "id": 29,
            "subscription_id": 2,
            "service": "SBB Halbtax",
            "period_start": "2026-02-01",
            "amount": 190.0,
            "paid_on": "2026-11-05",
            "method": "manual",
        }
        already_paid = client.post("/subscriptions/2/payments").json()
        assert already_paid["error"] == "already_paid"
        assert already_paid["field"] == "id"
        assert already_paid["message"]
        auto_pay = client.post("/subscriptions/1/payments").json()
        assert auto_pay["error"] == "auto_pay_subscription"
        assert auto_pay["field"] == "auto_pay"
        assert auto_pay["message"]


def test_future_manual_subscription_has_nothing_due(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        payload = {
            "service": "Future",
            "category_id": 5,
            "price": 10,
            "currency": "CHF",
            "billing_period": "monthly",
            "start_date": "2026-12-01",
            "auto_pay": False,
        }
        response = client.post("/subscriptions", json=payload)
        assert response.status_code == 201
        error = client.post(f"/subscriptions/{response.json()['id']}/payments").json()
        assert error["error"] == "nothing_due"
        assert error["field"] == "start_date"
        assert error["message"]


def test_turning_on_autopay_keeps_earlier_period_manual(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        assert client.patch("/subscriptions/2", json={"auto_pay": True}).status_code == 200
        assert client.get("/subscriptions/2").json()["payment_status"] == "pending"
        assert client.post("/subscriptions/2/payments").status_code == 201


def test_cancel_and_end_subscription(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(database_file) as client:
        response = client.post("/subscriptions/1/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        assert response.json()["cancelled_at"] == "2026-11-05"
        assert response.json()["ends_on"] == "2026-11-12"
        assert response.json()["next_charge_date"] is None
        listing = client.get("/subscriptions").json()
        assert [item["service"] for item in listing["subscriptions"]] == [
            "Netflix",
            "SBB Halbtax",
            "Spotify",
        ]
        assert listing["monthly_total"] == 30.78
        assert listing["cancelled_excluded"] == 1
        already_cancelled = client.post("/subscriptions/1/cancel").json()
        assert already_cancelled["error"] == "already_cancelled"
        assert already_cancelled["field"] == "id"
        assert already_cancelled["message"]
        cancelled = client.patch("/subscriptions/1", json={"price": 20}).json()
        assert cancelled["error"] == "subscription_cancelled"
        assert cancelled["field"] == "id"
        assert cancelled["message"]
        assert client.post("/subscriptions/999/cancel").status_code == 404

    with client_for(database_file, date(2026, 11, 12)) as client:
        assert client.get("/subscriptions/1").json()["status"] == "ended"
        assert "Netflix" not in [
            item["service"] for item in client.get("/subscriptions").json()["subscriptions"]
        ]
        assert len(
            [item for item in client.get("/history?type=payment").json()["items"] if item["service"] == "Netflix"]
        ) == 14


def test_future_cancel_ends_today_and_delete_removes_history(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(database_file) as client:
        payload = {
            "service": "Future",
            "category_id": 5,
            "price": 10,
            "currency": "CHF",
            "billing_period": "monthly",
            "start_date": "2026-12-01",
            "auto_pay": True,
            "notification_enabled": True,
        }
        future = client.post("/subscriptions", json=payload).json()
        assert client.post(f"/subscriptions/{future['id']}/cancel").json()["ends_on"] == "2026-11-05"
        assert client.delete("/subscriptions/1").status_code == 204
        assert not [item for item in client.get("/history").json()["items"] if item["service"] == "Netflix"]


def test_settings_and_notifications(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(database_file, date(2026, 11, 12)) as client:
        notifications = client.get("/notifications").json()
        assert notifications == {
            "count": 1,
            "message": "1 payment needs attention: SBB Halbtax",
            "items": [
                {
                    "subscription_id": 2,
                    "service": "SBB Halbtax",
                    "reason": "payment_overdue",
                    "date": "2026-02-01",
                }
            ],
        }
        assert client.post("/notifications/2/dismiss").json() == {
            "count": 0,
            "message": None,
            "items": [],
        }
        dismissed = client.post("/notifications/2/dismiss")
        assert dismissed.status_code == 409
        assert dismissed.json()["error"] == "nothing_to_dismiss"
        assert dismissed.json()["field"] == "subscription_id"
        assert dismissed.json()["message"]

    with client_for(database_file, date(2027, 1, 28)) as client:
        notifications = client.get("/notifications").json()
        assert notifications["items"] == [
            {
                "subscription_id": 2,
                "service": "SBB Halbtax",
                "reason": "upcoming_payment",
                "date": "2027-02-01",
            }
        ]

    database_file = tmp_path / "paid.sqlite"
    with client_for(database_file, date(2026, 11, 12)) as client:
        assert client.post("/subscriptions/2/payments").status_code == 201
    with client_for(database_file, date(2027, 1, 28)) as client:
        assert client.get("/notifications").json()["items"][0]["reason"] == "upcoming_payment"

    with client_for(tmp_path / "off.sqlite", date(2026, 11, 12)) as client:
        assert client.patch("/subscriptions/2", json={"notification_enabled": False}).status_code == 200
        assert client.get("/notifications").json()["count"] == 0

    database_file = tmp_path / "new.sqlite"
    with client_for(database_file, date(2026, 11, 12)) as client:
        created = client.post(
            "/subscriptions",
            json={
                "service": "Local Gym",
                "category_id": 4,
                "price": 60,
                "billing_period": "monthly",
                "start_date": "2026-11-15",
                "auto_pay": False,
                "notification_enabled": True,
            },
        ).json()
        items = client.get("/notifications").json()["items"]
        gym_item = next(item for item in items if item["service"] == "Local Gym")
        assert gym_item == {
            "subscription_id": created["id"],
            "service": "Local Gym",
            "reason": "upcoming_payment",
            "date": "2026-11-15",
        }
        assert client.patch("/settings", json={"reminder_days": 2}).status_code == 200
        assert "Local Gym" not in [
            item["service"] for item in client.get("/notifications").json()["items"]
        ]


def test_history_order_and_filters(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(database_file) as client:
        history = client.get("/history").json()["items"]
        assert len(history) == 28
        assert history[0]["service"] == "Spotify"
        assert history[0]["date"] == "2026-11-03"
        client.post("/subscriptions/1/cancel")
        history = client.get("/history").json()["items"]
        assert history[0]["type"] == "cancellation"
        assert history[0]["service"] == "Netflix"
        assert history[0]["ends_on"] == "2026-11-12"
        assert len(client.get("/history?type=cancellation").json()["items"]) == 1
        error = client.get("/history?type=foo").json()
        assert error["error"] == "invalid_input"
        assert error["field"] == "type"
        assert error["message"]
