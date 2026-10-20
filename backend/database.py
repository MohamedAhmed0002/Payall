import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import event, inspect
from sqlmodel import Session, SQLModel, create_engine

from models import Subscription, User


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
        subscriptions = []
        for row in seed["subscriptions"]:
            row["start_date"] = date.fromisoformat(row["start_date"])
            subscriptions.append(Subscription(**row))
        session.add_all(subscriptions)
