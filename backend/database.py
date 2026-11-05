import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import event, inspect
from sqlmodel import Session, SQLModel, create_engine, select

from models import Category, Subscription, User


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
    new_schema = not inspect(engine).has_table("user")
    SQLModel.metadata.create_all(engine)
    if not new_schema:
        return

    seed = json.loads(Path(__file__).with_name("seed.json").read_text(encoding="utf-8"))
    with Session(engine) as session, session.begin():
        user_data = seed["user"]
        user_data["created_at"] = datetime.fromisoformat(user_data["created_at"].replace("Z", "+00:00"))
        session.add(User(**user_data))
        session.flush()
        category_names = [
            "Entertainment",
            "Music",
            "Transport",
            "Health & Fitness",
            "Software & Cloud",
            "News & Media",
            "Education",
            "Utilities",
            "Other",
        ]
        session.add_all([Category(name=name) for name in category_names])
        session.flush()
        categories = {category.name: category.id for category in session.exec(select(Category)).all()}
        subscriptions = []
        for row in seed["subscriptions"]:
            row["start_date"] = date.fromisoformat(row["start_date"])
            row["category_id"] = categories[row.pop("category")]
            row["price_rappen"] = int(Decimal(str(row.pop("price"))) * 100)
            subscriptions.append(Subscription(**row))
        session.add_all(subscriptions)
