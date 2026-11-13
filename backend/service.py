import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlmodel import Session, select

from models import (
    Category,
    CatalogItem,
    Payment,
    PaymentOutput,
    HistoryCancellation,
    HistoryOutput,
    HistoryPayment,
    NotificationItem,
    NotificationOutput,
    NextChargeOutput,
    SettingsOutput,
    SettingsUpdate,
    Subscription,
    UserSubscription,
    SubscriptionInput,
    SubscriptionList,
    SubscriptionOutput,
    SubscriptionUpdate,
    User,
)
from errors import PAYALL_ERROR_MESSAGES, PayallError
from rates import RateFetcher, get_rate


CURRENT_USER_ID = 1


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _period_date(start_date: date, billing_period: str, periods: int) -> date:
    if billing_period == "weekly":
        return start_date + timedelta(weeks=periods)
    return _add_months(start_date, periods * (1 if billing_period == "monthly" else 12))


def charge_dates(subscription: UserSubscription, until: date) -> list[date]:
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


def _one_year_after(value: date) -> date:
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


def get_own_subscription(session: Session, subscription_id: int) -> UserSubscription:
    subscription = session.exec(
        select(UserSubscription).where(
            UserSubscription.id == subscription_id,
            UserSubscription.user_id == CURRENT_USER_ID,
        )
    ).first()
    if subscription is None:
        raise PayallError("subscription_not_found", "id", status=404)
    return subscription


def record_due_autopay_payments(session: Session, today: date) -> None:
    """Mock replacement for a payment provider or nightly job: an automatic payment is assumed to succeed on its charge date."""
    subscriptions = session.exec(
        select(UserSubscription).where(
            UserSubscription.user_id == CURRENT_USER_ID,
            UserSubscription.auto_pay,
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
            if (
                subscription.auto_pay_since is not None
                and period_start >= subscription.auto_pay_since
                and period_start not in existing
            ):
                try:
                    rate, rate_date = get_rate(
                        session,
                        subscription.currency,
                        period_start,
                        session.info.get("rate_fetcher"),
                    )
                except PayallError as error:
                    if error.code == "exchange_rate_unavailable":
                        continue
                    raise
                session.add(
                    _new_payment(subscription, period_start, period_start, "auto", rate, rate_date)
                )
                changed = True
    if changed:
        session.commit()


def _period_start(subscription: UserSubscription, today: date) -> date | None:
    dates = charge_dates(subscription, today)
    return dates[-1] if dates else None


def _payment_status(session: Session, subscription: UserSubscription, today: date) -> str:
    period_start = _period_start(subscription, today)
    if period_start is not None and period_start < subscription.tracked_since:
        return "paid"
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


def _service_name(session: Session, subscription: UserSubscription) -> str:
    return subscription.service


def _new_payment(
    subscription: UserSubscription,
    period_start: date,
    paid_on: date,
    method: str,
    rate: Decimal,
    rate_date: date,
) -> Payment:
    rate_millionths = int((rate * Decimal(1_000_000)).to_integral_value())
    amount_chf_rappen = int(
        (from_rappen(subscription.price_rappen) * rate * 100).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )
    return Payment(
        subscription_id=subscription.id,
        period_start=period_start,
        amount_rappen=subscription.price_rappen,
        currency=subscription.currency,
        amount_chf_rappen=amount_chf_rappen,
        chf_per_unit_millionths=rate_millionths,
        rate_date=rate_date,
        paid_on=paid_on,
        method=method,
    )


def _payment_output(session: Session, payment: Payment) -> PaymentOutput:
    subscription = session.get(UserSubscription, payment.subscription_id)
    return PaymentOutput(
        id=payment.id,
        subscription_id=payment.subscription_id,
        service=_service_name(session, subscription),
        period_start=payment.period_start,
        amount=from_rappen(payment.amount_rappen),
        currency=payment.currency,
        amount_chf=from_rappen(payment.amount_chf_rappen),
        exchange_rate=Decimal(payment.chf_per_unit_millionths) / Decimal(1_000_000),
        paid_on=payment.paid_on,
        method=payment.method,
    )


def _to_output(session: Session, subscription: UserSubscription, today: date) -> SubscriptionOutput:
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
    payment_status = _payment_status(session, subscription, today)
    return SubscriptionOutput(
        id=subscription.id,
        user_id=subscription.user_id,
        service=subscription.service,
        category_id=subscription.category_id,
        category=category.name,
        price=from_rappen(subscription.price_rappen),
        currency=subscription.currency,
        billing_period=subscription.billing_period,
        start_date=subscription.start_date,
        auto_pay=subscription.auto_pay,
        next_charge_date=next_date,
        payment_status=payment_status,
        status=status,
        catalog_id=subscription.subscription_id,
        is_custom=subscription.subscription_id is None,
        cancelled_at=subscription.cancelled_at,
        ends_on=subscription.ends_on,
        notification_enabled=subscription.notification_enabled,
    )


def create_subscription(session: Session, payload: SubscriptionInput, today: date) -> SubscriptionOutput:
    record_due_autopay_payments(session, today)
    if payload.price is not None and payload.price <= 0:
        raise PayallError("price_must_be_positive", "price")
    if payload.price is not None and payload.price > Decimal("100000.00"):
        raise PayallError("price_too_high", "price")
    if not date(2000, 1, 1) <= payload.start_date <= _one_year_after(today):
        raise PayallError("start_date_out_of_range", "start_date")

    details = None
    if payload.catalog_id is not None:
        details = session.get(Subscription, payload.catalog_id)
        if details is None:
            raise PayallError("catalog_item_not_found", "catalog_id")
        service = payload.service.strip() if payload.service else details.name
        category_id = payload.category_id if payload.category_id is not None else details.category_id
        price = payload.price if payload.price is not None else from_rappen(details.default_price_rappen)
        billing_period = payload.billing_period or details.billing_period
    else:
        service = (payload.service or "").strip()
        if not service:
            raise PayallError("service_name_required", "service")
        if len(service) > 100:
            raise PayallError("service_name_too_long", "service")
        category_id = payload.category_id
        if category_id is None or session.get(Category, category_id) is None:
            raise PayallError("category_not_found", "category_id")
        if payload.price is None:
            raise PayallError("price_required", "price")
        if payload.billing_period is None:
            raise PayallError("billing_period_required", "billing_period")
        price = payload.price
        billing_period = payload.billing_period
    if category_id is None or session.get(Category, category_id) is None:
        raise PayallError("category_not_found", "category_id")
    subscription = UserSubscription(
        user_id=CURRENT_USER_ID,
        service=service,
        category_id=category_id,
        subscription_id=payload.catalog_id,
        price_rappen=to_rappen(price),
        currency=payload.currency,
        billing_period=billing_period,
        start_date=payload.start_date,
        tracked_since=today,
        auto_pay=payload.auto_pay,
        auto_pay_since=today if payload.auto_pay else None,
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


def list_catalog(session: Session) -> list[CatalogItem]:
    rows = session.exec(
        select(Subscription, Category)
        .join(Category, Subscription.category_id == Category.id)
        .order_by(Subscription.id)
    ).all()
    return [
        CatalogItem(
            id=subscription.id,
            name=subscription.name,
            category_id=subscription.category_id,
            category=category.name,
            default_price=from_rappen(subscription.default_price_rappen),
            billing_period=subscription.billing_period,
        )
        for subscription, category in rows
    ]


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
        select(UserSubscription)
        .where(
            UserSubscription.user_id == CURRENT_USER_ID,
            UserSubscription.notification_enabled,
        )
        .order_by(UserSubscription.id)
    ).all()
    items = []
    reminder_end = today + timedelta(days=settings.reminder_days)
    for subscription in subscriptions:
        output = _to_output(session, subscription, today)
        if output.status != "active":
            continue
        current_period = _period_start(subscription, today)
        notification_next_charge = output.next_charge_date
        if (
            output.payment_status == "paid"
            and current_period is not None
            and notification_next_charge == current_period
        ):
            notification_next_charge = next_charge_date(
                subscription.start_date,
                subscription.billing_period,
                today + timedelta(days=1),
            )
        autopay_covers_current = (
            current_period is not None
            and subscription.auto_pay
            and subscription.auto_pay_since is not None
            and current_period >= subscription.auto_pay_since
        )
        overdue_date = None
        if current_period is not None and not autopay_covers_current:
            if output.payment_status == "pending":
                overdue_date = current_period
        notification_date = (
            overdue_date
            if overdue_date != subscription.reminder_dismissed_for
            else None
        )
        reason = (
            "payment_overdue"
            if overdue_date is not None and overdue_date < today
            else "upcoming_payment"
            if overdue_date == today
            else None
        )
        if notification_date is None and notification_next_charge is not None:
            if today <= notification_next_charge <= reminder_end and not autopay_covers_current:
                if notification_next_charge != subscription.reminder_dismissed_for:
                    notification_date = notification_next_charge
                    reason = "upcoming_payment"
        if notification_date is None or notification_date == subscription.reminder_dismissed_for:
            continue
        items.append(
            NotificationItem(
                subscription_id=subscription.id,
                service=_service_name(session, subscription),
                reason=reason,
                date=notification_date,
            )
        )
    names = ", ".join(item.service for item in items)
    message = None
    if items:
        noun = "payment" if len(items) == 1 else "payments"
        verb = "needs" if len(items) == 1 else "need"
        message = f"{len(items)} {noun} {verb} attention: {names}"
    return NotificationOutput(count=len(items), message=message, items=items)


def dismiss_notification(
    session: Session, subscription_id: int, today: date
) -> NotificationOutput:
    subscription = get_own_subscription(session, subscription_id)
    notifications = list_notifications(session, today)
    current = next(
        (item for item in notifications.items if item.subscription_id == subscription.id),
        None,
    )
    if current is None:
        raise PayallError("nothing_to_dismiss", "subscription_id", status=409)
    subscription.reminder_dismissed_for = current.date
    session.add(subscription)
    session.commit()
    return list_notifications(session, today)


def list_history(session: Session, event_type: str | None, today: date) -> HistoryOutput:
    record_due_autopay_payments(session, today)
    if event_type not in (None, "payment", "cancellation"):
        raise PayallError("invalid_input", "type")
    history = []
    if event_type in (None, "payment"):
        rows = session.exec(
            select(Payment, UserSubscription)
            .join(UserSubscription, Payment.subscription_id == UserSubscription.id)
            .where(UserSubscription.user_id == CURRENT_USER_ID)
        ).all()
        history.extend(
            (
                payment.paid_on,
                payment.id,
                HistoryPayment(
                    type="payment",
                    date=payment.paid_on,
                    subscription_id=subscription.id,
                    service=_service_name(session, subscription),
                    amount=from_rappen(payment.amount_rappen),
                    currency=payment.currency,
                    amount_chf=from_rappen(payment.amount_chf_rappen),
                    exchange_rate=Decimal(payment.chf_per_unit_millionths) / Decimal(1_000_000),
                    method=payment.method,
                ),
            )
            for payment, subscription in rows
        )
    if event_type in (None, "cancellation"):
        subscriptions = session.exec(
            select(UserSubscription).where(
                UserSubscription.user_id == CURRENT_USER_ID,
                UserSubscription.cancelled_at.is_not(None),
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
                    service=_service_name(session, subscription),
                    ends_on=subscription.ends_on,
                ),
            )
            for subscription in subscriptions
        )
    history.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return HistoryOutput(items=[item[2] for item in history])


def list_subscriptions(
    session: Session,
    today: date,
    search: str | None = None,
    sort: str = "id",
    order: str = "asc",
    rate_fetcher: RateFetcher | None = None,
) -> SubscriptionList:
    record_due_autopay_payments(session, today)
    sort = sort or "id"
    cleaned_search = search.strip() if search else ""
    if len(cleaned_search) > 100:
        raise PayallError("invalid_input", "search")
    query = (
        select(UserSubscription)
        .join(Category, Category.id == UserSubscription.category_id)
        .where(UserSubscription.user_id == CURRENT_USER_ID)
    )
    if cleaned_search:
        escaped_search = (
            cleaned_search.lower()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = f"%{escaped_search}%"
        query = query.where(
            (func.lower(UserSubscription.service).like(pattern, escape="\\"))
            | (func.lower(Category.name).like(pattern, escape="\\"))
        )
    if sort == "price":
        primary = UserSubscription.price_rappen.desc() if order == "desc" else UserSubscription.price_rappen.asc()
        query = query.order_by(primary, UserSubscription.id.asc())
    elif sort == "service":
        service_column = func.lower(UserSubscription.service)
        primary = service_column.desc() if order == "desc" else service_column.asc()
        query = query.order_by(primary, UserSubscription.id.asc())
    else:
        primary = UserSubscription.id.desc() if order == "desc" else UserSubscription.id.asc()
        query = query.order_by(primary)
    all_subscriptions = session.exec(query).all()
    outputs = [_to_output(session, item, today) for item in all_subscriptions]
    visible = [_to_output(session, item, today) for item in session.exec(
        select(UserSubscription).where(UserSubscription.user_id == CURRENT_USER_ID).order_by(UserSubscription.id)
    ).all()]
    visible = [item for item in visible if item.status != "ended"]
    subscriptions = [item for item in outputs if item.status != "ended"]
    if sort == "next_charge_date":
        with_date = [item for item in subscriptions if item.next_charge_date is not None]
        without_date = [item for item in subscriptions if item.next_charge_date is None]
        with_date.sort(key=lambda item: item.id)
        with_date.sort(key=lambda item: item.next_charge_date, reverse=order == "desc")
        subscriptions = with_date + without_date
    active = [item for item in visible if item.status == "active"]
    monthly_total = Decimal(0)
    annual_total = Decimal(0)
    rate_dates: list[date] = []
    rates_missing = 0
    for item in active:
        try:
            rate, rate_date = get_rate(session, item.currency, today, rate_fetcher)
        except PayallError as error:
            if error.code != "exchange_rate_unavailable":
                raise
            rates_missing += 1
            continue
        if item.currency != "CHF":
            rate_dates.append(rate_date)
        monthly_total += (
            item.price
            * rate
            * {"monthly": Decimal(1), "yearly": Decimal(1) / 12, "weekly": Decimal(52) / 12}[item.billing_period]
        )
        annual_total += (
            item.price
            * rate
            * {"monthly": Decimal(12), "yearly": Decimal(1), "weekly": Decimal(52)}[item.billing_period]
        )
    monthly_total = monthly_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    annual_total = annual_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    next_charge = min(
        (
            item
            for item in visible
            if item.status == "active" and item.next_charge_date is not None
        ),
        key=lambda item: (item.next_charge_date, item.id),
        default=None,
    )
    user = session.get(User, CURRENT_USER_ID)
    return SubscriptionList(
        subscriptions=subscriptions,
        monthly_total=monthly_total,
        annual_total=annual_total,
        next_charge=(
            NextChargeOutput(
                subscription_id=next_charge.id,
                service=next_charge.service,
                date=next_charge.next_charge_date,
                amount=next_charge.price,
                currency=next_charge.currency,
            )
            if next_charge is not None
            else None
        ),
        currency=user.currency if user else "CHF",
        cancelled_excluded=sum(item.status == "cancelled" for item in visible),
        totals_approximate=any(item.currency != "CHF" for item in active),
        rates_as_of=min(rate_dates) if rate_dates else None,
        rates_missing=rates_missing,
    )


def edit_subscription(session: Session, subscription_id: int, payload: SubscriptionUpdate, today: date) -> SubscriptionOutput:
    record_due_autopay_payments(session, today)
    subscription = get_own_subscription(session, subscription_id)
    if subscription.cancelled_at is not None:
        raise PayallError("subscription_cancelled", "id", status=409)
    updates = payload.model_dump(exclude_unset=True)
    client_fields = set(updates)
    if "price" in updates:
        if updates["price"] is None or updates["price"] <= 0:
            raise PayallError("price_must_be_positive", "price")
        if updates["price"] > Decimal("100000.00"):
            raise PayallError("price_too_high", "price")
    if "service" in updates:
        if updates["service"] is None or not updates["service"].strip():
            raise PayallError("service_name_required", "service")
        updates["service"] = updates["service"].strip()
        if len(updates["service"]) > 100:
            raise PayallError("service_name_too_long", "service")
    if "start_date" in updates and updates["start_date"] is not None:
        if not date(2000, 1, 1) <= updates["start_date"] <= _one_year_after(today):
            raise PayallError("start_date_out_of_range", "start_date")
    if "category_id" in updates and (
        updates["category_id"] is None or session.get(Category, updates["category_id"]) is None
    ):
        raise PayallError("category_not_found", "category_id")
    if "service" in updates:
        subscription.service = updates.pop("service")
    if "category_id" in updates:
        subscription.category_id = updates.pop("category_id")
    if "price" in updates:
        updates["price_rappen"] = to_rappen(updates.pop("price"))
    if "billing_period" in updates and updates["billing_period"] != subscription.billing_period:
        if "start_date" not in updates:
            updates["start_date"] = next_charge_date(subscription.start_date, subscription.billing_period, today)
    if "auto_pay" in updates and updates["auto_pay"] != subscription.auto_pay:
        updates["auto_pay_since"] = today if updates["auto_pay"] else None
    try:
        for field, value in updates.items():
            if field in client_fields and value is None:
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
    period_start = _period_start(subscription, today)
    if period_start is not None and period_start < subscription.tracked_since:
        raise PayallError("already_paid", "id", status=409)
    if subscription.auto_pay and (
        subscription.auto_pay_since is None
        or period_start is None
        or period_start >= subscription.auto_pay_since
    ):
        raise PayallError("auto_pay_subscription", "auto_pay", status=409)
    if period_start is None:
        raise PayallError("nothing_due", "start_date", status=409)
    if session.exec(
        select(Payment).where(
            Payment.subscription_id == subscription.id,
            Payment.period_start == period_start,
        )
    ).first():
        raise PayallError("already_paid", "id", status=409)
    rate, rate_date = get_rate(
        session,
        subscription.currency,
        today,
        session.info.get("rate_fetcher"),
    )
    payment = _new_payment(subscription, period_start, today, "manual", rate, rate_date)
    try:
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return _payment_output(session, payment)
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
    try:
        session.commit()
        session.refresh(subscription)
        return _to_output(session, subscription, today)
    except Exception:
        session.rollback()
        raise


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
