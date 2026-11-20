import json
import os
from pathlib import Path

from sqlalchemy import Boolean, Column, ForeignKey, Integer, MetaData, String, Table, create_engine
from sqlalchemy.engine import make_url

DOMAIN = json.loads(Path(__file__).with_name("domain.json").read_text(encoding="utf-8"))
METADATA = MetaData(
    naming_convention={
        "pk": "pk_%(table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s",
    }
)
TYPES = {"text": String(200), "integer": Integer, "boolean": Boolean}
TABLES = {}
for entity in DOMAIN["entities"]:
    key = entity["id"]
    columns = [Column("id", Integer, primary_key=True)]
    for field, kind in entity["fields"].items():
        reference = entity["relations"].get(field)
        constraints = [ForeignKey(f"{reference}.id")] if reference else []
        columns.append(
            Column(field, TYPES[kind], *constraints, nullable=False, unique=field in entity["unique"])
        )
    TABLES[key] = Table(key, METADATA, *columns)


def setting(name):
    file = os.environ.get(name + "_FILE")
    return Path(file).read_text(encoding="utf-8").strip() if file else os.environ.get(name)


def database_url():
    value = setting("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL or DATABASE_URL_FILE is required")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use PostgreSQL with the psycopg driver")
    return url


def connect():
    return create_engine(database_url(), pool_pre_ping=True, hide_parameters=True)
