import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import event, inspect
from sqlmodel import Session, SQLModel, create_engine, select

from models import Category, UserSubscription, User


def make_engine(database_file: Path, *, echo: bool = False):
    database_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        "sqlite:///" + database_file.resolve().as_posix(),
        connect_args={"check_same_thread": False},
        echo=echo,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def initialise(engine):
    inspector = inspect(engine)
    new_schema = not inspector.has_table("user")
    if inspector.has_table("subscription") and not inspector.has_table("usersubscription"):
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE subscription RENAME TO usersubscription")
    SQLModel.metadata.create_all(engine)
    if not new_schema:
        return

    seed = json.loads(Path(__file__).with_name("seed.json").read_text(encoding="utf-8"))
    with Session(engine) as session, session.begin():
        user_data = seed["user"]
        user_data["created_at"] = datetime.fromisoformat(user_data["created_at"].replace("Z", "+00:00"))
        session.add(User(**user_data))
        session.flush()
        session.add_all([Category(name=name) for name in seed["categories"]])
        session.flush()
        categories = {category.name: category.id for category in session.exec(select(Category)).all()}
        subscriptions = []
        for row in seed["subscriptions"]:
            row["start_date"] = date.fromisoformat(row["start_date"])
            row["tracked_since"] = date.fromisoformat(row["tracked_since"])
            if row.get("auto_pay_since") is not None:
                row["auto_pay_since"] = date.fromisoformat(row["auto_pay_since"])
            row["category_id"] = categories[row.pop("category")]
            row["price_rappen"] = int(Decimal(str(row.pop("price"))) * 100)
            subscriptions.append(UserSubscription(**row))
        session.add_all(subscriptions)
