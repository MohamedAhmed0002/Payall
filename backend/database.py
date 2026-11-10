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
    if inspector.has_table("usersubscription"):
        columns = {column["name"] for column in inspector.get_columns("usersubscription")}
        if "is_custom" in columns and "service_name" not in columns:
            with engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                connection.commit()
                transaction = connection.begin()
                try:
                    connection.exec_driver_sql(
                        """
                        CREATE TABLE usersubscription_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL REFERENCES user(id),
                            subscription_id INTEGER REFERENCES subscription(id),
                            service_name VARCHAR,
                            category_id INTEGER REFERENCES category(id),
                            price_rappen INTEGER NOT NULL CHECK (price_rappen > 0),
                            currency VARCHAR NOT NULL,
                            billing_period VARCHAR NOT NULL CHECK (billing_period IN ('weekly', 'monthly', 'yearly')),
                            start_date DATE NOT NULL,
                            tracked_since DATE NOT NULL,
                            auto_pay BOOLEAN NOT NULL,
                            auto_pay_since DATE,
                            cancelled_at DATE,
                            ends_on DATE,
                            notification_enabled BOOLEAN NOT NULL
                        )
                        """
                    )
                    connection.exec_driver_sql(
                        """
                        INSERT INTO usersubscription_new (
                            id, user_id, subscription_id, service_name, category_id,
                            price_rappen, currency, billing_period, start_date,
                            tracked_since, auto_pay, auto_pay_since, cancelled_at,
                            ends_on, notification_enabled
                        )
                        SELECT
                            us.id,
                            us.user_id,
                            CASE WHEN us.is_custom THEN NULL ELSE us.subscription_id END,
                            CASE WHEN us.is_custom THEN s.service ELSE NULL END,
                            CASE WHEN us.is_custom THEN CAST(s.category_id AS INTEGER) ELSE NULL END,
                            us.price_rappen, us.currency, us.billing_period, us.start_date,
                            us.tracked_since, us.auto_pay, us.auto_pay_since, us.cancelled_at,
                            us.ends_on, us.notification_enabled
                        FROM usersubscription us
                        LEFT JOIN subscription s ON s.id = us.subscription_id
                        """
                    )
                    connection.exec_driver_sql("DROP TABLE usersubscription")
                    connection.exec_driver_sql(
                        "ALTER TABLE usersubscription_new RENAME TO usersubscription"
                    )
                    transaction.commit()
                except Exception:
                    transaction.rollback()
                    raise
                finally:
                    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    SQLModel.metadata.create_all(engine)
    inspector = inspect(engine)
    user_subscription_columns = {
        column["name"] for column in inspector.get_columns("usersubscription")
    }
    if "service_name" not in user_subscription_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE usersubscription ADD COLUMN service_name VARCHAR")
    if "category_id" not in user_subscription_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE usersubscription ADD COLUMN category_id INTEGER REFERENCES category(id)")
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
        subscription_rows = []
        for row in seed["catalog"]:
            subscription_rows.append(
                Subscription(
                    id=row["id"],
                    service=row["service"],
                    category_id=str(categories[row["category"]]),
                )
            )
        session.add_all(subscription_rows)
        user_subscriptions = []
        for row in seed["user_subscriptions"]:
            row["start_date"] = date.fromisoformat(row["start_date"])
            row["tracked_since"] = date.fromisoformat(row["tracked_since"])
            if row.get("auto_pay_since") is not None:
                row["auto_pay_since"] = date.fromisoformat(row["auto_pay_since"])
            row["price_rappen"] = int(Decimal(str(row.pop("price"))) * 100)
            user_subscriptions.append(UserSubscription(**row))
        session.add_all(user_subscriptions)
