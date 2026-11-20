import os
from hmac import compare_digest
from typing import Annotated

from db import DOMAIN, TABLES, connect, setting
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, create_model
from rules import apply_rules, calculate
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

app = FastAPI(title=DOMAIN["title"])
engine = connect()
bearer = HTTPBearer(auto_error=False)
VALUE_TYPES = {
    "text": Annotated[str, Field(max_length=200)],
    "integer": Annotated[int, Field(ge=-2147483648, le=2147483647)],
    "boolean": bool,
}


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    token = setting("TWIN_API_TOKEN")
    if token:
        if not credentials or not compare_digest(credentials.credentials.encode(), token.encode()):
            raise HTTPException(401, "Valid API token required")
    elif os.environ.get("TWIN_LOCAL_DEMO") != "1":
        raise HTTPException(503, "Authentication has not been configured")


@app.get("/api/health")
def health():
    try:
        with engine.connect() as connection:
            for table in TABLES.values():
                connection.execute(select(table.c.id).limit(1))
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database or migrations unavailable") from exc
    return {"status": "ok"}


def register(entity):
    key = entity["id"]
    table = TABLES[key]
    rules = [rule for rule in DOMAIN["rules"] if rule["entity"] == key]
    derived = {rule["field"] for rule in rules if rule["operator"] == "multiply"}
    fields = {field: (VALUE_TYPES[kind], ...) for field, kind in entity["fields"].items()}
    input_model = create_model(
        f"{key}_input",
        __base__=Payload,
        **{field: value for field, value in fields.items() if field not in derived},
    )
    record_model = create_model(f"{key}_record", __base__=Payload, id=(int, ...), **fields)

    def validated(payload):
        values = payload.model_dump()
        errors = apply_rules(key, values, rules)
        if errors:
            raise HTTPException(422, errors)
        try:
            return calculate(key, values, rules)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def preview(payload: input_model):
        return validated(payload)

    def create(payload: input_model):
        values = validated(payload)
        try:
            with engine.begin() as connection:
                row = connection.execute(insert(table).values(**values).returning(table)).mappings().one()
                return dict(row)
        except IntegrityError as exc:
            raise HTTPException(409, "Record conflicts with a unique field or required reference") from exc

    def records(limit: Annotated[int, Query(ge=1, le=100)] = 25, offset: Annotated[int, Query(ge=0)] = 0):
        with engine.connect() as connection:
            rows = connection.execute(
                select(table).order_by(table.c.id.desc()).limit(limit).offset(offset)
            ).mappings()
            return [dict(row) for row in rows]

    path = f"/api/{key}"
    auth = [Depends(authorize)]
    app.add_api_route(path + "/preview", preview, methods=["POST"], dependencies=auth, name=f"preview_{key}")
    app.add_api_route(
        path,
        create,
        methods=["POST"],
        dependencies=auth,
        status_code=201,
        response_model=record_model,
        name=f"create_{key}",
    )
    app.add_api_route(
        path,
        records,
        methods=["GET"],
        dependencies=auth,
        response_model=list[record_model],
        name=f"list_{key}",
    )


for entity in DOMAIN["entities"]:
    register(entity)

if frontend := os.environ.get("TWIN_FRONTEND_DIST"):
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
