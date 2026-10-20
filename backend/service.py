import calendar
from datetime import date, timedelta

from sqlmodel import Session, select

from models import Subscription, SubscriptionInput, SubscriptionList, SubscriptionOutput, User


# Temporary: replaced by the logged-in user once POST /login exists.
CURRENT_USER_ID = 1


class PayallError(Exception):
    def __init__(self, code: str, field: str, status: int = 422):
        self.code = code
        self.field = field
        self.status = status
        super().__init__(code)


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_charge_date(start_date: date, billing_period: str, today: date) -> date:
    if start_date >= today:
        return start_date

    if billing_period == "weekly":
        elapsed_weeks = (today - start_date).days // 7
        candidate = start_date + timedelta(weeks=elapsed_weeks)
        return candidate if candidate >= today else candidate + timedelta(weeks=1)

    months = 1 if billing_period == "monthly" else 12
    periods = 0
    candidate = start_date
    while candidate < today:
        periods += 1
        candidate = _add_months(start_date, periods * months)
    return candidate


def _to_output(subscription: Subscription) -> SubscriptionOutput:
    return SubscriptionOutput.model_validate(subscription, from_attributes=True)


def create_subscription(
    session: Session, payload: SubscriptionInput, today: date
) -> SubscriptionOutput:
    if payload.price <= 0:
        raise PayallError("price_must_be_positive", "price")
    if not payload.service.strip():
        raise PayallError("service_name_required", "service")
    if not payload.category.strip():
        raise PayallError("category_required", "category")

    subscription = Subscription(
        user_id=CURRENT_USER_ID,
        service=payload.service.strip(),
        is_custom=payload.is_custom,
        category=payload.category.strip(),
        price=payload.price,
        currency=payload.currency,
        billing_period=payload.billing_period,
        start_date=payload.start_date,
        next_charge_date=next_charge_date(payload.start_date, payload.billing_period, today),
        payment_status="pending",
        notification_enabled=payload.notification_enabled,
    )
    try:
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        return _to_output(subscription)
    except Exception:
        session.rollback()
        raise


def list_subscriptions(session: Session) -> SubscriptionList:
    subscriptions = session.exec(
        select(Subscription)
        .where(Subscription.user_id == CURRENT_USER_ID)
        .order_by(Subscription.id)
    ).all()
    user = session.get(User, CURRENT_USER_ID)
    monthly_total = sum(
        subscription.price
        * {"monthly": 1, "yearly": 1 / 12, "weekly": 52 / 12}[subscription.billing_period]
        for subscription in subscriptions
    )
    return SubscriptionList(
        subscriptions=[_to_output(subscription) for subscription in subscriptions],
        monthly_total=round(monthly_total, 2),
        currency=user.currency if user else "CHF",
    )
