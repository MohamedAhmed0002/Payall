from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "user"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True)
    currency: str = "CHF"
    created_at: datetime


class Subscription(SQLModel, table=True):
    __tablename__ = "subscription"
    __table_args__ = (
        CheckConstraint("price_rappen > 0"),
        CheckConstraint("billing_period IN ('weekly', 'monthly', 'yearly')"),
        CheckConstraint("payment_status IN ('paid', 'pending')"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    service: str
    is_custom: bool
    category_id: int = Field(foreign_key="category.id", index=True)
    price_rappen: int
    currency: str
    billing_period: str
    start_date: date
    payment_status: str
    notification_enabled: bool


class Category(SQLModel, table=True):
    __tablename__ = "category"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)


class SubscriptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    service: str
    is_custom: bool = False
    category_id: int
    price: Decimal
    currency: Literal["CHF"]
    billing_period: Literal["weekly", "monthly", "yearly"]
    start_date: date
    notification_enabled: bool = False

    @field_validator("price")
    @classmethod
    def validate_price_precision(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("Price must have at most 2 decimal places")
        return value

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> float:
        return float(value)


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    service: str | None = None
    category_id: int | None = None
    price: Decimal | None = None
    currency: Literal["CHF"] | None = None
    billing_period: Literal["weekly", "monthly", "yearly"] | None = None
    start_date: date | None = None
    notification_enabled: bool | None = None

    @field_validator("price")
    @classmethod
    def validate_price_precision(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value.as_tuple().exponent < -2:
            raise ValueError("Price must have at most 2 decimal places")
        return value


class SubscriptionOutput(SubscriptionInput):
    id: int
    user_id: int
    category: str
    next_charge_date: date
    payment_status: Literal["paid", "pending"]


class Error(BaseModel):
    error: str
    field: str
    message: str | None = None


class SubscriptionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriptions: list[SubscriptionOutput]
    monthly_total: Decimal
    currency: str

    @field_serializer("monthly_total")
    def serialize_monthly_total(self, value: Decimal) -> float:
        return float(value)
