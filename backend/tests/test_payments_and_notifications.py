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
        assert client.post("/subscriptions/2/payments").json() == {
            "error": "already_paid",
            "field": "id",
        }
        assert client.post("/subscriptions/1/payments").json() == {
            "error": "auto_pay_subscription",
            "field": "auto_pay",
        }


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
        assert client.post(f"/subscriptions/{response.json()['id']}/payments").json() == {
            "error": "nothing_due",
            "field": "start_date",
        }


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
        assert client.post("/subscriptions/1/cancel").json() == {
            "error": "already_cancelled",
            "field": "id",
        }
        assert client.patch("/subscriptions/1", json={"price": 20}).json() == {
            "error": "subscription_cancelled",
            "field": "id",
        }
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
    with client_for(tmp_path / "payall.sqlite") as client:
        assert client.get("/settings").json() == {"reminder_days": 7, "currency": "CHF"}
        notifications = client.get("/notifications").json()
        assert notifications["count"] == 2
        assert notifications["items"] == [
            {
                "subscription_id": 1,
                "service": "Netflix",
                "reason": "upcoming_charge",
                "date": "2026-11-12",
            },
            {
                "subscription_id": 2,
                "service": "SBB Halbtax",
                "reason": "payment_pending",
                "date": "2026-02-01",
            },
        ]
        assert notifications["message"] == "2 renewals need attention: Netflix, SBB Halbtax"
        assert client.post("/subscriptions/2/payments").status_code == 201
        assert client.get("/notifications").json()["message"] == "1 renewal needs attention: Netflix"
        assert client.patch("/settings", json={"reminder_days": 3}).status_code == 200
        assert client.get("/notifications").json()["count"] == 0
        assert client.patch("/settings", json={"reminder_days": 0}).json()["field"] == "reminder_days"
        assert client.patch("/settings", json={"reminder_days": 31}).json()["field"] == "reminder_days"
        assert client.patch("/settings", json={"unknown": 1}).status_code == 422
        assert client.patch("/settings", json={"reminder_days": 7}).status_code == 200
        assert client.post("/subscriptions/1/cancel").status_code == 200
        assert client.get("/notifications").json() == {"count": 0, "message": None, "items": []}
        assert client.get("/subscriptions/3").json()["notification_enabled"] is False


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
        assert client.get("/history?type=foo").json() == {
            "error": "invalid_input",
            "field": "type",
        }
