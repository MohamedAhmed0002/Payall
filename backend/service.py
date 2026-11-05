import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlmodel import Session, select

from models import (
    Category,
    Subscription,
    SubscriptionInput,
    SubscriptionList,
    SubscriptionOutput,
    SubscriptionUpdate,
    User,
)


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


def to_rappen(value: Decimal) -> int:
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def from_rappen(value: int) -> Decimal:
    return Decimal(value) / Decimal(100)


def get_own_subscription(session: Session, subscription_id: int) -> Subscription:
    subscription = session.exec(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.user_id == CURRENT_USER_ID,
        )
    ).first()
    if subscription is None:
        raise PayallError("subscription_not_found", "id", status=404)
    return subscription


def _to_output(session: Session, subscription: Subscription, today: date) -> SubscriptionOutput:
    category = session.get(Category, subscription.category_id)
    if category is None:
        raise PayallError("category_not_found", "category_id")
    return SubscriptionOutput(
        id=subscription.id,
        user_id=subscription.user_id,
        service=subscription.service,
        is_custom=subscription.is_custom,
        category_id=subscription.category_id,
        category=category.name,
        price=from_rappen(subscription.price_rappen),
        currency=subscription.currency,
        billing_period=subscription.billing_period,
        start_date=subscription.start_date,
        next_charge_date=next_charge_date(
            subscription.start_date, subscription.billing_period, today
        ),
        payment_status=subscription.payment_status,
        notification_enabled=subscription.notification_enabled,
    )


def create_subscription(
    session: Session, payload: SubscriptionInput, today: date
) -> SubscriptionOutput:
    if payload.price <= 0:
        raise PayallError("price_must_be_positive", "price")
    if not payload.service.strip():
        raise PayallError("service_name_required", "service")
    category = session.get(Category, payload.category_id)
    if category is None:
        raise PayallError("category_not_found", "category_id")

    subscription = Subscription(
        user_id=CURRENT_USER_ID,
        service=payload.service.strip(),
        is_custom=payload.is_custom,
        category_id=payload.category_id,
        price_rappen=to_rappen(payload.price),
        currency=payload.currency,
        billing_period=payload.billing_period,
        start_date=payload.start_date,
        payment_status="pending",
        notification_enabled=payload.notification_enabled,
    )
    try:
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        return _to_output(session, subscription, today)
    except Exception:
        session.rollback()
        raise


def read_subscription(
    session: Session, subscription_id: int, today: date
) -> SubscriptionOutput:
    return _to_output(session, get_own_subscription(session, subscription_id), today)


def list_categories(session: Session) -> list[Category]:
    return session.exec(select(Category).order_by(Category.id)).all()


def list_subscriptions(session: Session, today: date) -> SubscriptionList:
    subscriptions = session.exec(
        select(Subscription)
        .where(Subscription.user_id == CURRENT_USER_ID)
        .order_by(Subscription.id)
    ).all()
    user = session.get(User, CURRENT_USER_ID)
    monthly_values = (
        (
            from_rappen(subscription.price_rappen)
            * {
                "monthly": Decimal(1),
                "yearly": Decimal(1) / 12,
                "weekly": Decimal(52) / 12,
            }[subscription.billing_period]
        )
        for subscription in subscriptions
    )
    monthly_total = sum(monthly_values, Decimal(0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return SubscriptionList(
        subscriptions=[_to_output(session, subscription, today) for subscription in subscriptions],
        monthly_total=monthly_total,
        currency=user.currency if user else "CHF",
    )


def edit_subscription(
    session: Session,
    subscription_id: int,
    payload: SubscriptionUpdate,
    today: date,
) -> SubscriptionOutput:
    subscription = get_own_subscription(session, subscription_id)

    updates = payload.model_dump(exclude_unset=True)
    if "price" in updates and (updates["price"] is None or updates["price"] <= 0):
        raise PayallError("price_must_be_positive", "price")
    if "service" in updates:
        if updates["service"] is None or not updates["service"].strip():
            raise PayallError("service_name_required", "service")
        updates["service"] = updates["service"].strip()
    if "category_id" in updates:
        if updates["category_id"] is None or session.get(Category, updates["category_id"]) is None:
            raise PayallError("category_not_found", "category_id")
    if "price" in updates:
        updates["price_rappen"] = to_rappen(updates.pop("price"))
    if "billing_period" in updates and updates["billing_period"] != subscription.billing_period:
        if "start_date" not in updates:
            updates["start_date"] = next_charge_date(
                subscription.start_date, subscription.billing_period, today
            )

    try:
        for field, value in updates.items():
            if value is None:
                raise PayallError("invalid_input", field)
            setattr(subscription, field, value)
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        return _to_output(session, subscription, today)
    except Exception:
        session.rollback()
        raise


def delete_subscription(session: Session, subscription_id: int) -> None:
    subscription = get_own_subscription(session, subscription_id)

    try:
        session.delete(subscription)
        session.commit()
    except Exception:
        session.rollback()
        raise
