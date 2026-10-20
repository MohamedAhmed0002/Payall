from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True)
    currency: str = "CHF"
    created_at: datetime


class Subscription(SQLModel, table=True):
    __tablename__ = "subscription"
    __table_args__ = (
        CheckConstraint("price > 0"),
        CheckConstraint("billing_period IN ('weekly', 'monthly', 'yearly')"),
        CheckConstraint("payment_status IN ('paid', 'pending')"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    service: str
    is_custom: bool
    category: str
    price: float
    currency: str
    billing_period: str
    start_date: date
    next_charge_date: date
    payment_status: str
    notification_enabled: bool


class SubscriptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    is_custom: bool = False
    category: str
    price: float
    currency: Literal["CHF"]
    billing_period: Literal["weekly", "monthly", "yearly"]
    start_date: date
    notification_enabled: bool = False


class SubscriptionOutput(SubscriptionInput):
    id: int
    user_id: int
    next_charge_date: date
    payment_status: Literal["paid", "pending"]


class SubscriptionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriptions: list[SubscriptionOutput]
    monthly_total: float
    currency: str
