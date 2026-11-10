from datetime import date
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app


def client_for(database_file: Path, current_date: date = date(2026, 11, 5)) -> TestClient:
    return TestClient(create_app(database_file, today=lambda: current_date))


def services(response):
    return [item["service"] for item in response.json()["subscriptions"]]


def test_search_matches_service_and_category(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        assert services(client.get("/subscriptions?search=net")) == ["Netflix"]
        assert services(client.get("/subscriptions?search=NETFLIX")) == ["Netflix"]
        assert services(client.get("/subscriptions?search=music")) == ["Spotify"]
        assert services(client.get("/subscriptions?search=transport")) == ["SBB Halbtax"]
        response = client.get("/subscriptions?search=xyz").json()
        assert response["subscriptions"] == []
        assert response["monthly_total"] == 49.68
        assert len(client.get("/subscriptions?search=%20%20").json()["subscriptions"]) == 3


def test_sorting_and_ordering(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        assert services(client.get("/subscriptions?sort=next_charge_date")) == [
            "Netflix",
            "Spotify",
            "SBB Halbtax",
        ]
        assert services(client.get("/subscriptions?sort=next_charge_date&order=desc")) == [
            "SBB Halbtax",
            "Spotify",
            "Netflix",
        ]
        assert services(client.get("/subscriptions?sort=price")) == [
            "Spotify",
            "Netflix",
            "SBB Halbtax",
        ]
        assert services(client.get("/subscriptions?sort=service")) == [
            "Netflix",
            "SBB Halbtax",
            "Spotify",
        ]
        assert [item["id"] for item in client.get("/subscriptions?order=desc").json()["subscriptions"]] == [3, 2, 1]


def test_cancelled_subscriptions_sort_last_by_next_charge_date(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        assert client.post("/subscriptions/1/cancel").status_code == 200
        assert services(client.get("/subscriptions?sort=next_charge_date")) == [
            "Spotify",
            "SBB Halbtax",
            "Netflix",
        ]
        assert services(client.get("/subscriptions?sort=next_charge_date&order=desc")) == [
            "SBB Halbtax",
            "Spotify",
            "Netflix",
        ]


def test_invalid_search_and_sort_parameters(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        for query, field in (
            ("/subscriptions?sort=foo", "sort"),
            ("/subscriptions?order=up", "order"),
            ("/subscriptions?search=" + "x" * 101, "search"),
        ):
            response = client.get(query)
            assert response.status_code == 422
            body = response.json()
            assert body["error"] == "invalid_input"
            assert body["field"] == field
            assert body["message"]


def test_switching_autopay_off_allows_later_manual_payment(tmp_path):
    database_file = tmp_path / "payall.sqlite"
    with client_for(database_file) as client:
        response = client.patch("/subscriptions/1", json={"auto_pay": False})
        assert response.status_code == 200
        assert response.json()["auto_pay"] is False
    with client_for(database_file, date(2026, 12, 12)) as client:
        subscription = client.get("/subscriptions/1").json()
        assert subscription["payment_status"] == "pending"
        assert client.post("/subscriptions/1/payments").status_code == 201


def test_autopay_activation_does_not_hide_pending_period(tmp_path):
    with client_for(tmp_path / "payall.sqlite") as client:
        assert client.patch("/subscriptions/2", json={"auto_pay": True}).status_code == 200
        items = client.get("/notifications").json()["items"]
        assert "SBB Halbtax" not in [item["service"] for item in items]
