from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from sqlalchemy import CheckConstraint, Column, String, UniqueConstraint
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint("reminder_days BETWEEN 1 AND 30"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True)
    currency: str = "CHF"
    reminder_days: int = 7
    created_at: datetime


class UserSubscription(SQLModel, table=True):
    __tablename__ = "usersubscription"
    __table_args__ = (
        CheckConstraint("price_rappen > 0"),
        CheckConstraint("billing_period IN ('weekly', 'monthly', 'yearly')"),
        CheckConstraint("payment_status IN ('paid', 'pending')"),
        CheckConstraint("status IN ('active', 'cancelled', 'ended')"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    subscription_id: int = Field(foreign_key="subscription.id", index=True)
    price_rappen: int
    currency: str
    billing_period: str
    start_date: date
    next_charge_date: date | None = None
    payment_status: str = "pending"
    status: str = "active"
    tracked_since: date
    auto_pay: bool
    auto_pay_since: date | None = None
    cancelled_at: date | None = None
    ends_on: date | None = None
    notification_enabled: bool


class Subscription(SQLModel, table=True):
    __tablename__ = "subscription"
    __table_args__ = (
        CheckConstraint("default_price_rappen > 0"),
        CheckConstraint("billing_period IN ('weekly', 'monthly', 'yearly')"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column("service", String, nullable=False))
    category_id: int = Field(foreign_key="category.id", index=True)
    default_price_rappen: int = Field(gt=0)
    billing_period: str
    default_price_is_sample: bool = False


class Payment(SQLModel, table=True):
    __tablename__ = "payment"
    __table_args__ = (
        CheckConstraint("amount_rappen > 0"),
        CheckConstraint("method IN ('auto', 'manual')"),
        UniqueConstraint("subscription_id", "period_start"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    subscription_id: int = Field(foreign_key="usersubscription.id", index=True)
    period_start: date
    amount_rappen: int
    paid_on: date
    method: str


class Category(SQLModel, table=True):
    __tablename__ = "category"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)


class SubscriptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    subscription_id: int | None = None
    service: str | None = None
    category_id: int | None = None
    price: Decimal | None = None
    currency: Literal["CHF"] = "CHF"
    billing_period: Literal["weekly", "monthly", "yearly"] | None = None
    start_date: date
    auto_pay: bool
    notification_enabled: bool = False

    @field_validator("price")
    @classmethod
    def validate_price_precision(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value.as_tuple().exponent < -2:
            raise ValueError("Price must have at most 2 decimal places")
        return value

    @field_serializer("price")
    def serialize_price(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    service: str | None = None
    category_id: int | None = None
    price: Decimal | None = None
    currency: Literal["CHF"] | None = None
    billing_period: Literal["weekly", "monthly", "yearly"] | None = None
    start_date: date | None = None
    auto_pay: bool | None = None
    notification_enabled: bool | None = None

    @field_validator("price")
    @classmethod
    def validate_price_precision(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value.as_tuple().exponent < -2:
            raise ValueError("Price must have at most 2 decimal places")
        return value


class SubscriptionOutput(BaseModel):
    id: int
    user_id: int
    category: str
    service: str
    category_id: int
    price: Decimal
    currency: Literal["CHF"]
    billing_period: Literal["weekly", "monthly", "yearly"]
    start_date: date
    auto_pay: bool
    next_charge_date: date | None
    payment_status: Literal["paid", "pending"]
    status: Literal["active", "cancelled", "ended"]
    cancelled_at: date | None
    ends_on: date | None
    notification_enabled: bool

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> float:
        return float(value)


class CatalogItem(BaseModel):
    id: int
    name: str
    category_id: int
    category: str
    default_price: Decimal
    billing_period: Literal["weekly", "monthly", "yearly"]
    default_price_is_sample: bool

    @field_serializer("default_price")
    def serialize_default_price(self, value: Decimal) -> float:
        return float(value)


class Error(BaseModel):
    error: str
    field: str
    message: str | None = None


class SubscriptionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriptions: list[SubscriptionOutput]
    monthly_total: Decimal
    currency: str
    cancelled_excluded: int

    @field_serializer("monthly_total")
    def serialize_monthly_total(self, value: Decimal) -> float:
        return float(value)


class PaymentOutput(BaseModel):
    id: int
    subscription_id: int
    service: str
    period_start: date
    amount: Decimal
    paid_on: date
    method: Literal["auto", "manual"]

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class SettingsOutput(BaseModel):
    reminder_days: int
    currency: str


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminder_days: int


class NotificationItem(BaseModel):
    subscription_id: int
    service: str
    reason: Literal["payment_pending", "upcoming_charge"]
    date: date


class NotificationOutput(BaseModel):
    count: int
    message: str | None
    items: list[NotificationItem]


class HistoryPayment(BaseModel):
    type: Literal["payment"]
    date: date
    subscription_id: int
    service: str
    amount: Decimal
    method: Literal["auto", "manual"]

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class HistoryCancellation(BaseModel):
    type: Literal["cancellation"]
    date: date
    subscription_id: int
    service: str
    ends_on: date


HistoryItem = HistoryPayment | HistoryCancellation


class HistoryOutput(BaseModel):
    items: list[HistoryItem]
