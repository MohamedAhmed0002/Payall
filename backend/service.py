import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlmodel import Session, select

from models import (
    Category,
    Payment,
    PaymentOutput,
    HistoryCancellation,
    HistoryOutput,
    HistoryPayment,
    NotificationItem,
    NotificationOutput,
    SettingsOutput,
    SettingsUpdate,
    Subscription,
    SubscriptionInput,
    SubscriptionList,
    SubscriptionOutput,
    SubscriptionUpdate,
    User,
)


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
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _period_date(start_date: date, billing_period: str, periods: int) -> date:
    if billing_period == "weekly":
        return start_date + timedelta(weeks=periods)
    return _add_months(start_date, periods * (1 if billing_period == "monthly" else 12))


def charge_dates(subscription: Subscription, until: date) -> list[date]:
    if subscription.start_date > until:
        return []
    dates = []
    periods = 0
    while True:
        charge_date = _period_date(subscription.start_date, subscription.billing_period, periods)
        if charge_date > until:
            return dates
        if subscription.ends_on is None or charge_date < subscription.ends_on:
            dates.append(charge_date)
        periods += 1


def next_charge_date(start_date: date, billing_period: str, today: date) -> date:
    candidate = _period_date(start_date, billing_period, 0)
    periods = 0
    while candidate < today:
        periods += 1
        candidate = _period_date(start_date, billing_period, periods)
    return candidate


def _first_charge_after(start_date: date, billing_period: str, today: date) -> date:
    periods = 0
    candidate = start_date
    while candidate <= today:
        periods += 1
        candidate = _period_date(start_date, billing_period, periods)
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


def record_due_autopay_payments(session: Session, today: date) -> None:
    """Mock replacement for a payment provider or nightly job: an automatic payment is assumed to succeed on its charge date."""
    subscriptions = session.exec(
        select(Subscription).where(
            Subscription.user_id == CURRENT_USER_ID,
            Subscription.auto_pay,
        )
    ).all()
    changed = False
    for subscription in subscriptions:
        existing = {
            payment.period_start
            for payment in session.exec(
                select(Payment).where(Payment.subscription_id == subscription.id)
            ).all()
        }
        for period_start in charge_dates(subscription, today):
            if period_start not in existing:
                session.add(
                    Payment(
                        subscription_id=subscription.id,
                        period_start=period_start,
                        amount_rappen=subscription.price_rappen,
                        paid_on=period_start,
                        method="auto",
                    )
                )
                changed = True
    if changed:
        session.commit()


def _period_start(subscription: Subscription, today: date) -> date | None:
    dates = charge_dates(subscription, today)
    return dates[-1] if dates else None


def _payment_status(session: Session, subscription: Subscription, today: date) -> str:
    period_start = _period_start(subscription, today)
    if period_start is None:
        payment = session.exec(
            select(Payment).where(Payment.subscription_id == subscription.id)
        ).first()
    else:
        payment = session.exec(
            select(Payment).where(
                Payment.subscription_id == subscription.id,
                Payment.period_start == period_start,
            )
        ).first()
    return "paid" if payment else "pending"


def _to_output(session: Session, subscription: Subscription, today: date) -> SubscriptionOutput:
    category = session.get(Category, subscription.category_id)
    if category is None:
        raise PayallError("category_not_found", "category_id")
    next_date = None
    status = "active"
    if subscription.cancelled_at is not None:
        next_date = None
        status = "ended" if today >= subscription.ends_on else "cancelled"
    else:
        next_date = next_charge_date(subscription.start_date, subscription.billing_period, today)
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
        auto_pay=subscription.auto_pay,
        next_charge_date=next_date,
        payment_status=_payment_status(session, subscription, today),
        status=status,
        cancelled_at=subscription.cancelled_at,
        ends_on=subscription.ends_on,
        notification_enabled=subscription.notification_enabled,
    )


def create_subscription(session: Session, payload: SubscriptionInput, today: date) -> SubscriptionOutput:
    record_due_autopay_payments(session, today)
    if payload.price <= 0:
        raise PayallError("price_must_be_positive", "price")
    if not payload.service.strip():
        raise PayallError("service_name_required", "service")
    if session.get(Category, payload.category_id) is None:
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
        auto_pay=payload.auto_pay,
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


def read_subscription(session: Session, subscription_id: int, today: date) -> SubscriptionOutput:
    record_due_autopay_payments(session, today)
    return _to_output(session, get_own_subscription(session, subscription_id), today)


def list_categories(session: Session) -> list[Category]:
    return session.exec(select(Category).order_by(Category.id)).all()


def read_settings(session: Session) -> SettingsOutput:
    user = session.get(User, CURRENT_USER_ID)
    if user is None:
        raise PayallError("user_not_found", "id", status=404)
    return SettingsOutput(reminder_days=user.reminder_days, currency=user.currency)


def update_settings(session: Session, payload: SettingsUpdate) -> SettingsOutput:
    if not 1 <= payload.reminder_days <= 30:
        raise PayallError("invalid_input", "reminder_days")
    user = session.get(User, CURRENT_USER_ID)
    if user is None:
        raise PayallError("user_not_found", "id", status=404)
    user.reminder_days = payload.reminder_days
    session.add(user)
    session.commit()
    session.refresh(user)
    return SettingsOutput(reminder_days=user.reminder_days, currency=user.currency)


def list_notifications(session: Session, today: date) -> NotificationOutput:
    record_due_autopay_payments(session, today)
    settings = read_settings(session)
    subscriptions = session.exec(
        select(Subscription)
        .where(
            Subscription.user_id == CURRENT_USER_ID,
            Subscription.notification_enabled,
        )
        .order_by(Subscription.id)
    ).all()
    items = []
    for subscription in subscriptions:
        output = _to_output(session, subscription, today)
        if output.status != "active":
            continue
        period_start = _period_start(subscription, today)
        if output.payment_status == "pending" and not subscription.auto_pay and period_start is not None:
            items.append(
                NotificationItem(
                    subscription_id=subscription.id,
                    service=subscription.service,
                    reason="payment_pending",
                    date=period_start,
                )
            )
        elif output.next_charge_date is not None and output.next_charge_date <= today + timedelta(days=settings.reminder_days):
            items.append(
                NotificationItem(
                    subscription_id=subscription.id,
                    service=subscription.service,
                    reason="upcoming_charge",
                    date=output.next_charge_date,
                )
            )
    names = ", ".join(item.service for item in items)
    message = None
    if items:
        noun = "renewal" if len(items) == 1 else "renewals"
        verb = "needs" if len(items) == 1 else "need"
        message = f"{len(items)} {noun} {verb} attention: {names}"
    return NotificationOutput(count=len(items), message=message, items=items)


def list_history(session: Session, event_type: str | None, today: date) -> HistoryOutput:
    record_due_autopay_payments(session, today)
    if event_type not in (None, "payment", "cancellation"):
        raise PayallError("invalid_input", "type")
    history = []
    if event_type in (None, "payment"):
        rows = session.exec(
            select(Payment, Subscription)
            .join(Subscription, Payment.subscription_id == Subscription.id)
            .where(Subscription.user_id == CURRENT_USER_ID)
        ).all()
        history.extend(
            (
                payment.paid_on,
                payment.id,
                HistoryPayment(
                    type="payment",
                    date=payment.paid_on,
                    subscription_id=subscription.id,
                    service=subscription.service,
                    amount=from_rappen(payment.amount_rappen),
                    method=payment.method,
                ),
            )
            for payment, subscription in rows
        )
    if event_type in (None, "cancellation"):
        subscriptions = session.exec(
            select(Subscription).where(
                Subscription.user_id == CURRENT_USER_ID,
                Subscription.cancelled_at.is_not(None),
            )
        ).all()
        history.extend(
            (
                subscription.cancelled_at,
                subscription.id,
                HistoryCancellation(
                    type="cancellation",
                    date=subscription.cancelled_at,
                    subscription_id=subscription.id,
                    service=subscription.service,
                    ends_on=subscription.ends_on,
                ),
            )
            for subscription in subscriptions
        )
    history.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return HistoryOutput(items=[item[2] for item in history])


def list_subscriptions(session: Session, today: date) -> SubscriptionList:
    record_due_autopay_payments(session, today)
    all_subscriptions = session.exec(
        select(Subscription)
        .where(Subscription.user_id == CURRENT_USER_ID)
        .order_by(Subscription.id)
    ).all()
    outputs = [_to_output(session, item, today) for item in all_subscriptions]
    subscriptions = [item for item in outputs if item.status != "ended"]
    active = [item for item in subscriptions if item.status == "active"]
    monthly_total = sum(
        (
            item.price
            * {"monthly": Decimal(1), "yearly": Decimal(1) / 12, "weekly": Decimal(52) / 12}[item.billing_period]
            for item in active
        ),
        Decimal(0),
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    user = session.get(User, CURRENT_USER_ID)
    return SubscriptionList(
        subscriptions=subscriptions,
        monthly_total=monthly_total,
        currency=user.currency if user else "CHF",
        cancelled_excluded=sum(item.status == "cancelled" for item in subscriptions),
    )


def edit_subscription(session: Session, subscription_id: int, payload: SubscriptionUpdate, today: date) -> SubscriptionOutput:
    record_due_autopay_payments(session, today)
    subscription = get_own_subscription(session, subscription_id)
    if subscription.cancelled_at is not None:
        raise PayallError("subscription_cancelled", "id", status=409)
    updates = payload.model_dump(exclude_unset=True)
    if "price" in updates and (updates["price"] is None or updates["price"] <= 0):
        raise PayallError("price_must_be_positive", "price")
    if "service" in updates:
        if updates["service"] is None or not updates["service"].strip():
            raise PayallError("service_name_required", "service")
        updates["service"] = updates["service"].strip()
    if "category_id" in updates and (
        updates["category_id"] is None or session.get(Category, updates["category_id"]) is None
    ):
        raise PayallError("category_not_found", "category_id")
    if "price" in updates:
        updates["price_rappen"] = to_rappen(updates.pop("price"))
    if "billing_period" in updates and updates["billing_period"] != subscription.billing_period:
        if "start_date" not in updates:
            updates["start_date"] = next_charge_date(subscription.start_date, subscription.billing_period, today)
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


def mark_subscription_paid(session: Session, subscription_id: int, today: date) -> PaymentOutput:
    record_due_autopay_payments(session, today)
    subscription = get_own_subscription(session, subscription_id)
    if subscription.auto_pay:
        raise PayallError("auto_pay_subscription", "auto_pay", status=409)
    period_start = _period_start(subscription, today)
    if period_start is None:
        raise PayallError("nothing_due", "start_date", status=409)
    if session.exec(
        select(Payment).where(
            Payment.subscription_id == subscription.id,
            Payment.period_start == period_start,
        )
    ).first():
        raise PayallError("already_paid", "id", status=409)
    payment = Payment(
        subscription_id=subscription.id,
        period_start=period_start,
        amount_rappen=subscription.price_rappen,
        paid_on=today,
        method="manual",
    )
    try:
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return PaymentOutput(
            id=payment.id,
            subscription_id=subscription.id,
            service=subscription.service,
            period_start=payment.period_start,
            amount=from_rappen(payment.amount_rappen),
            paid_on=payment.paid_on,
            method=payment.method,
        )
    except Exception:
        session.rollback()
        raise


def cancel_subscription(session: Session, subscription_id: int, today: date) -> SubscriptionOutput:
    record_due_autopay_payments(session, today)
    subscription = get_own_subscription(session, subscription_id)
    if subscription.cancelled_at is not None:
        raise PayallError("already_cancelled", "id", status=409)
    subscription.cancelled_at = today
    subscription.ends_on = (
        _first_charge_after(subscription.start_date, subscription.billing_period, today)
        if subscription.start_date <= today
        else today
    )
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return _to_output(session, subscription, today)


def delete_subscription(session: Session, subscription_id: int, today: date) -> None:
    record_due_autopay_payments(session, today)
    subscription = get_own_subscription(session, subscription_id)
    try:
        for payment in session.exec(
            select(Payment).where(Payment.subscription_id == subscription.id)
        ).all():
            session.delete(payment)
        session.delete(subscription)
        session.commit()
    except Exception:
        session.rollback()
        raise
