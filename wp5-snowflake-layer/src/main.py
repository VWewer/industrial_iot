from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from . import snowflake_client as sf_module
from .ingestion.mes_webhook import router as mes_router
from .ingestion.mqtt_subscriber import MQTTSubscriber
from .ingestion.sap_puller import SAPPuller
from .query_api import router as query_router
from .scheduler import TransformScheduler
from .seed_loader import load_if_empty
from .transforms.gold import run_gold
from .transforms.silver import run_silver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
)
log = logging.getLogger(__name__)

_REQUIRED_ENV = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_WAREHOUSE",
]

_sql_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "sql"))
_seed_dir = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "contracts", "seed-data")
)


def _check_env() -> None:
    missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
    if missing:
        log.error("Missing required environment variables: %s", missing)
        sys.exit(1)


def _init_schema(client) -> None:
    schema_path = os.path.join(_sql_dir, "init_schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    client.run_script(sql)
    log.info("Snowflake schema initialised")


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
    load_dotenv()
    _check_env()

    sf_client = sf_module.init(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        role=os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
    )
    _init_schema(sf_client)

    if os.getenv("LOAD_SEED_DATA", "true").lower() == "true":
        load_if_empty(seed_data_dir=_seed_dir, sql_dir=_sql_dir)

    mqtt = MQTTSubscriber(
        broker_host=os.getenv("MQTT_BROKER_HOST", "localhost"),
        broker_port=int(os.getenv("MQTT_BROKER_PORT", "1883")),
    )
    mqtt.connect()

    sap_puller = SAPPuller(
        sap_api_url=os.getenv("SAP_API_URL", "http://localhost:8003"),
        snowflake_client=sf_client,
    )

    def _silver() -> None:
        run_silver(_sql_dir)

    def _gold() -> None:
        run_gold(_sql_dir)

    scheduler = TransformScheduler(
        sap_puller=sap_puller,
        silver_fn=_silver,
        gold_fn=_gold,
        sap_interval_s=int(os.getenv("SAP_PULL_INTERVAL_S", "60")),
        transform_interval_s=int(os.getenv("TRANSFORM_INTERVAL_S", "30")),
    )
    scheduler.start()

    yield

    scheduler.stop()
    mqtt.disconnect()
    sf_client.close()


app = FastAPI(
    lifespan=lifespan,
    title="WP5 -- Snowflake Data Layer",
    description=(
        "Ingests sensor stream (C1), MES events (C10), and SAP reference data (C11) "
        "into Snowflake Bronze/Silver/Gold layers. Exposes Gold query API (C12)."
    ),
    version="1.0.0",
)

app.include_router(mes_router)
app.include_router(query_router)


if __name__ == "__main__":
    port = int(os.getenv("WP5_API_PORT", "8005"))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
