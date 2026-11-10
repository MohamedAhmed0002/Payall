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
    if "subscription_id" not in user_subscription_columns and {"service", "category_id"} <= user_subscription_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE usersubscription ADD COLUMN subscription_id INTEGER REFERENCES subscription(id)"
            )
            catalog_columns = {
                column["name"] for column in inspect(connection).get_columns("subscription")
            }
            rows = connection.exec_driver_sql(
                "SELECT id, service, category_id, price_rappen, billing_period FROM usersubscription"
            ).fetchall()
            for subscription_id, service, category_id, price_rappen, billing_period in rows:
                if {"service", "default_price_rappen", "billing_period"} <= catalog_columns:
                    connection.exec_driver_sql(
                        """
                        INSERT OR IGNORE INTO subscription (
                            id, service, category_id, default_price_rappen, billing_period,
                            default_price_is_sample
                        ) VALUES (?, ?, ?, ?, ?, 0)
                        """,
                        (subscription_id, service, category_id, price_rappen, billing_period),
                    )
                elif "service" in catalog_columns:
                    connection.exec_driver_sql(
                        "INSERT OR IGNORE INTO subscription (id, service, category_id) VALUES (?, ?, ?)",
                        (subscription_id, service, str(category_id)),
                    )
                else:
                    connection.exec_driver_sql(
                        """
                        INSERT OR IGNORE INTO subscription (
                            id, name, category_id, default_price_rappen, billing_period,
                            default_price_is_sample
                        ) VALUES (?, ?, ?, 999, 'monthly', 1)
                        """,
                        (subscription_id, service, category_id),
                    )
                connection.exec_driver_sql(
                    "UPDATE usersubscription SET subscription_id = ? WHERE id = ?",
                    (subscription_id, subscription_id),
                )
    seed = json.loads(Path(__file__).with_name("seed.json").read_text(encoding="utf-8"))
    catalog_columns = {column["name"] for column in inspect(engine).get_columns("subscription")}
    catalog_defaults_need_migration = (
        "default_price_rappen" not in catalog_columns
        or "billing_period" not in catalog_columns
        or "default_price_is_sample" not in catalog_columns
    )
    if "default_price_rappen" not in catalog_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE subscription ADD COLUMN default_price_rappen INTEGER NOT NULL DEFAULT 999"
            )
    if "billing_period" not in catalog_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE subscription ADD COLUMN billing_period VARCHAR NOT NULL DEFAULT 'monthly'"
            )
    if "default_price_is_sample" not in catalog_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE subscription ADD COLUMN default_price_is_sample BOOLEAN NOT NULL DEFAULT 1"
            )
    user_subscription_columns = {
        column["name"] for column in inspect(engine).get_columns("usersubscription")
    }
    for column, sql_type, default in (
        ("next_charge_date", "DATE", "NULL"),
        ("payment_status", "VARCHAR", "'pending'"),
        ("status", "VARCHAR", "'active'"),
    ):
        if column not in user_subscription_columns:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    f"ALTER TABLE usersubscription ADD COLUMN {column} {sql_type} DEFAULT {default}"
                )

    with Session(engine) as session, session.begin():
        user_data = seed["user"]
        if session.get(User, user_data["id"]) is None:
            user_data["created_at"] = datetime.fromisoformat(
                user_data["created_at"].replace("Z", "+00:00")
            )
            session.add(User(**user_data))
        existing_categories = {
            category.name for category in session.exec(select(Category)).all()
        }
        session.add_all(
            [
                Category(name=name)
                for name in seed["categories"]
                if name not in existing_categories
            ]
        )
        session.flush()
        session.flush()
        categories = {category.name: category.id for category in session.exec(select(Category)).all()}
        catalog_is_empty = session.exec(select(Subscription).limit(1)).first() is None
        if catalog_defaults_need_migration and not catalog_is_empty:
            for row in seed["catalog"]:
                catalog_entry = session.get(Subscription, row["id"])
                if catalog_entry is not None:
                    catalog_entry.default_price_rappen = int(
                        Decimal(str(row["default_price"])) * 100
                    )
                    catalog_entry.billing_period = row["billing_period"]
                    catalog_entry.default_price_is_sample = row["default_price_is_sample"]
        if catalog_is_empty:
            session.add_all(
                [
                    Subscription(
                        id=row["id"],
                        name=row["service"],
                        category_id=categories[row["category"]],
                        default_price_rappen=int(Decimal(str(row["default_price"])) * 100),
                        billing_period=row["billing_period"],
                        default_price_is_sample=row["default_price_is_sample"],
                    )
                    for row in seed["catalog"]
                ]
            )
        session.flush()
        orphan_subscriptions = []
        if {"service_name", "category_id"} <= user_subscription_columns:
            orphan_subscriptions = session.connection().exec_driver_sql(
                """
                SELECT id, service_name, category_id, price_rappen, billing_period
                FROM usersubscription
                WHERE subscription_id IS NULL
                """
            ).fetchall()
        for row_id, service_name, category_id, price_rappen, billing_period in orphan_subscriptions:
            if not service_name or category_id is None:
                raise ValueError(f"User subscription {row_id} cannot be linked to a catalog entry")
            catalog_entry = Subscription(
                name=service_name,
                category_id=category_id,
                default_price_rappen=price_rappen,
                billing_period=billing_period,
                default_price_is_sample=False,
            )
            session.add(catalog_entry)
            session.flush()
            session.connection().exec_driver_sql(
                "UPDATE usersubscription SET subscription_id = ? WHERE id = ?",
                (catalog_entry.id, row_id),
            )
        if new_schema:
            session.flush()
            user_subscriptions = []
            for row in seed["user_subscriptions"]:
                row["start_date"] = date.fromisoformat(row["start_date"])
                row["tracked_since"] = date.fromisoformat(row["tracked_since"])
                if row.get("auto_pay_since") is not None:
                    row["auto_pay_since"] = date.fromisoformat(row["auto_pay_since"])
                row["price_rappen"] = int(Decimal(str(row.pop("price"))) * 100)
                user_subscriptions.append(UserSubscription(**row))
            session.add_all(user_subscriptions)
