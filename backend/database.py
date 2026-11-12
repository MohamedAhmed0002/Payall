import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from models import Category, Subscription, User, UserSubscription


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
    SQLModel.metadata.create_all(engine)
    seed = json.loads(Path(__file__).with_name("seed.json").read_text(encoding="utf-8"))
    with Session(engine) as session, session.begin():
        user_data = seed["user"]
        if session.get(User, user_data["id"]) is None:
            user_data = {**user_data, "created_at": datetime.fromisoformat(
                user_data["created_at"].replace("Z", "+00:00")
            )}
            session.add(User(**user_data))

        existing_categories = {category.name for category in session.exec(select(Category)).all()}
        session.add_all(
            [Category(name=name) for name in seed["categories"] if name not in existing_categories]
        )
        session.flush()
        categories = {category.name: category.id for category in session.exec(select(Category)).all()}

        if session.exec(select(Subscription).limit(1)).first() is None:
            session.add_all(
                [
                    Subscription(
                        id=row["id"],
                        name=row["service"],
                        category_id=categories[row["category"]],
                        default_price_rappen=int(Decimal(str(row["default_price"])) * 100),
                        billing_period=row["billing_period"],
                    )
                    for row in seed["catalog"]
                ]
            )
            session.flush()

        if session.exec(select(UserSubscription).limit(1)).first() is None:
            user_subscriptions = []
            for source in seed["user_subscriptions"]:
                row = {**source}
                row["start_date"] = date.fromisoformat(row["start_date"])
                row["tracked_since"] = date.fromisoformat(row["tracked_since"])
                if row.get("auto_pay_since") is not None:
                    row["auto_pay_since"] = date.fromisoformat(row["auto_pay_since"])
                row["price_rappen"] = int(Decimal(str(row.pop("price"))) * 100)
                user_subscriptions.append(UserSubscription(**row))
            session.add_all(user_subscriptions)
