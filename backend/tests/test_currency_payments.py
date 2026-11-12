from datetime import date
from decimal import Decimal
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import create_app
from models import Payment
from rates import fetch_rate


TODAY = date(2026, 11, 12)


def make_client(database_file, rate_fetcher, current_date=TODAY):
    return TestClient(
        create_app(
            database_file,
            today=lambda: current_date,
            rate_fetcher=rate_fetcher,
        )
    )


def currency_payload(currency, *, billing_period="monthly", auto_pay=False):
    return {
        "service": f"{currency} subscription",
        "category_id": 5,
        "price": 100.0,
        "currency": currency,
        "billing_period": billing_period,
        "start_date": "2026-11-12",
        "auto_pay": auto_pay,
    }


def test_manual_usd_payment_and_history_use_payment_rate(tmp_path):
    with make_client(tmp_path / "payall.sqlite", lambda _currency, _date: Decimal("0.80")) as client:
        subscription = client.post(
            "/subscriptions",
            json=currency_payload("USD"),
        ).json()
        payment = client.post(f"/subscriptions/{subscription['id']}/payments").json()
        history = client.get("/history?type=payment").json()["items"]

    assert payment["amount"] == 100.0
    assert payment["currency"] == "USD"
    assert payment["amount_chf"] == 80.0
    assert payment["exchange_rate"] == 0.8
    history_payment = next(item for item in history if item["subscription_id"] == subscription["id"])
    assert {
        key: history_payment[key]
        for key in ("amount", "currency", "amount_chf", "exchange_rate")
    } == {
        "amount": 100.0,
        "currency": "USD",
        "amount_chf": 80.0,
        "exchange_rate": 0.8,
    }


def test_weekly_eur_autopay_stores_rate_for_each_charge_date(tmp_path):
    def rate_for_date(_currency, on_date):
        return Decimal("0.90") if on_date.month == 11 else Decimal("1.10")

    database_file = tmp_path / "payall.sqlite"
    with make_client(database_file, rate_for_date) as client:
        subscription = client.post(
            "/subscriptions",
            json=currency_payload("EUR", billing_period="weekly", auto_pay=True),
        ).json()

    with make_client(database_file, rate_for_date, current_date=date(2026, 12, 10)) as client:
        client.get("/subscriptions")
        history = client.get("/history?type=payment").json()["items"]

    payments = [
        item for item in history
        if item["subscription_id"] == subscription["id"]
    ]
    payments.sort(key=lambda item: item["date"])
    assert [(item["date"], item["exchange_rate"]) for item in payments] == [
        ("2026-11-12", 0.9),
        ("2026-11-19", 0.9),
        ("2026-11-26", 0.9),
        ("2026-12-03", 1.1),
        ("2026-12-10", 1.1),
    ]


def test_manual_payment_without_rate_returns_503_and_saves_nothing(tmp_path):
    def unavailable(_currency, _date):
        raise RuntimeError("offline")

    database_file = tmp_path / "payall.sqlite"
    with make_client(database_file, unavailable) as client:
        subscription = client.post(
            "/subscriptions",
            json=currency_payload("USD"),
        ).json()
        response = client.post(f"/subscriptions/{subscription['id']}/payments")
        assert response.status_code == 503
        assert response.json()["error"] == "exchange_rate_unavailable"
        assert response.json()["message"]

    with Session(client.app.state.engine) as session:
        assert session.exec(
            select(Payment).where(Payment.subscription_id == subscription["id"])
        ).all() == []


def test_autopay_without_rate_retries_on_later_request(tmp_path):
    available = False

    def rate_fetcher(_currency, _date):
        if not available:
            raise RuntimeError("offline")
        return Decimal("0.80")

    database_file = tmp_path / "payall.sqlite"
    with make_client(database_file, rate_fetcher) as client:
        subscription = client.post(
            "/subscriptions",
            json=currency_payload("USD", auto_pay=True),
        ).json()

    with make_client(database_file, rate_fetcher, current_date=date(2026, 11, 19)) as client:
        assert client.get("/subscriptions").status_code == 200
        with Session(client.app.state.engine) as session:
            assert session.exec(
                select(Payment).where(Payment.subscription_id == subscription["id"])
            ).all() == []
        available = True
        assert client.get("/subscriptions").status_code == 200
        with Session(client.app.state.engine) as session:
            assert len(session.exec(
                select(Payment).where(Payment.subscription_id == subscription["id"])
            ).all()) == 1


def test_seed_chf_payments_store_chf_values(tmp_path):
    with make_client(tmp_path / "payall.sqlite", lambda *_args: Decimal("0.80")) as client:
        payments = client.get("/history?type=payment").json()["items"]

    assert payments
    assert all(
        item["currency"] == "CHF"
        and item["amount_chf"] == item["amount"]
        and item["exchange_rate"] == 1.0
        for item in payments
    )


def test_fetch_rate_uses_frankfurter_v1_request(monkeypatch):
    requests = []

    def mock_get(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(
            200,
            json={"rates": {"CHF": 0.8}},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", mock_get)
    assert fetch_rate("USD", date(2026, 11, 12)) == Decimal("0.8")
    url, kwargs = requests[0]
    assert url.endswith("/v1/2026-11-12")
    assert kwargs["params"] == {"base": "USD", "symbols": "CHF"}
    assert kwargs["follow_redirects"] is True
    assert kwargs["timeout"] == 5
