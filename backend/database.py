import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import event, inspect
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
    inspector = inspect(engine)
    new_schema = not inspector.has_table("user")
    if inspector.has_table("subscription") and not inspector.has_table("usersubscription"):
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE subscription RENAME TO usersubscription")
    SQLModel.metadata.create_all(engine)
    inspector = inspect(engine)
    user_subscription_columns = {
        column["name"] for column in inspector.get_columns("usersubscription")
    }
    if "subscription_id" not in user_subscription_columns and {"service", "category_id"} <= user_subscription_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE usersubscription ADD COLUMN subscription_id INTEGER REFERENCES subscription(id)"
            )
            rows = connection.exec_driver_sql(
                "SELECT id, service, category_id FROM usersubscription"
            ).fetchall()
            for subscription_id, service, category_id in rows:
                connection.exec_driver_sql(
                    "INSERT OR IGNORE INTO subscription (id, service, category_id) VALUES (?, ?, ?)",
                    (subscription_id, service, str(category_id)),
                )
                connection.exec_driver_sql(
                    "UPDATE usersubscription SET subscription_id = ? WHERE id = ?",
                    (subscription_id, subscription_id),
                )
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
            service = row.pop("service")
            category_id = categories[row.pop("category")]
            session.add(Subscription(id=row["id"], service=service, category_id=str(category_id)))
            row["start_date"] = date.fromisoformat(row["start_date"])
            row["tracked_since"] = date.fromisoformat(row["tracked_since"])
            if row.get("auto_pay_since") is not None:
                row["auto_pay_since"] = date.fromisoformat(row["auto_pay_since"])
            row["subscription_id"] = row["id"]
            row["price_rappen"] = int(Decimal(str(row.pop("price"))) * 100)
            subscriptions.append(UserSubscription(**row))
        session.add_all(subscriptions)
