import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlmodel import Session

from database import initialise, make_engine
from models import SubscriptionInput, SubscriptionList, SubscriptionOutput
from service import PayallError, create_subscription, list_subscriptions


def create_app(database_file: Path, *, echo: bool = False) -> FastAPI:
    engine = make_engine(database_file, echo=echo)

    @asynccontextmanager
    async def lifespan(_app):
        initialise(engine)
        yield
        engine.dispose()

    app = FastAPI(title="Payall backend", lifespan=lifespan)
    app.state.engine = engine

    def get_session():
        with Session(engine) as session:
            yield session

    DatabaseSession = Annotated[Session, Depends(get_session)]

    @app.exception_handler(PayallError)
    async def payall_error_handler(_request: Request, error: PayallError):
        return JSONResponse(
            status_code=error.status,
            content={"error": error.code, "field": error.field},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, error: RequestValidationError):
        detail = error.errors()[0]
        location = detail.get("loc", ())
        field = next((part for part in reversed(location) if isinstance(part, str)), "body")
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_input",
                "field": field,
                "message": detail.get("msg", "Invalid input"),
            },
        )

    @app.get("/subscriptions", response_model=SubscriptionList)
    def get_subscriptions(session: DatabaseSession):
        return list_subscriptions(session)

    @app.post("/subscriptions", response_model=SubscriptionOutput, status_code=201)
    def post_subscription(
        payload: SubscriptionInput, response: Response, session: DatabaseSession
    ):
        result = create_subscription(session, payload, date.today())
        response.headers["Location"] = f"/subscriptions/{result.id}"
        return result

    return app


app = create_app(
    Path(os.environ.get("PAYALL_DB", Path(__file__).parent / "data" / "payall.sqlite"))
)
