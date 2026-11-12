import os
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable

import httpx
from sqlmodel import Session, select

from errors import PayallError
from models import ExchangeRate


RateFetcher = Callable[[str, date], Decimal]
DEFAULT_RATES_URL = "https://api.frankfurter.dev/v1"


def fetch_rate(currency: str, on_date: date) -> Decimal:
    url = f"{os.getenv('PAYALL_RATES_URL', DEFAULT_RATES_URL).rstrip('/')}/{on_date}"
    response = httpx.get(
        url,
        params={"base": currency, "symbols": "CHF"},
        timeout=5,
        follow_redirects=True,
    )
    response.raise_for_status()
    value = response.json()["rates"]["CHF"]
    return Decimal(str(value))


def get_rate(
    session: Session,
    currency: str,
    on_date: date,
    rate_fetcher: RateFetcher | None = None,
) -> tuple[Decimal, date]:
    if currency == "CHF":
        return Decimal(1), on_date

    stored = session.exec(
        select(ExchangeRate).where(
            ExchangeRate.currency == currency,
            ExchangeRate.rate_date == on_date,
        )
    ).first()
    if stored is not None:
        return Decimal(stored.chf_per_unit_millionths) / Decimal(1_000_000), stored.rate_date

    fetch = rate_fetcher or fetch_rate
    try:
        value = fetch(currency, on_date)
        millionths = int((value * Decimal(1_000_000)).to_integral_value())
        if millionths <= 0:
            raise ValueError("Exchange rate must be positive")
    except (httpx.HTTPError, InvalidOperation, KeyError, TypeError, ValueError, RuntimeError):
        fallback = session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.currency == currency, ExchangeRate.rate_date <= on_date)
            .order_by(ExchangeRate.rate_date.desc())
        ).first()
        if fallback is None:
            fallback = session.exec(
                select(ExchangeRate)
                .where(ExchangeRate.currency == currency)
                .order_by(ExchangeRate.rate_date.desc())
            ).first()
        if fallback is None:
            raise PayallError("exchange_rate_unavailable", "currency", status=503)
        return (
            Decimal(fallback.chf_per_unit_millionths) / Decimal(1_000_000),
            fallback.rate_date,
        )

    stored = ExchangeRate(
        currency=currency,
        rate_date=on_date,
        chf_per_unit_millionths=millionths,
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(stored)
    session.commit()
    return value, on_date
