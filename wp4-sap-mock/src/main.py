"""
wp4-sap-mock/src/main.py

Entry point for WP4 SAP mock service.
Loads seed data on startup, mounts API router, starts uvicorn.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI

from . import api as api_module
from .data_store import DataStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    store = DataStore()
    store.load_seed_data()
    api_module.store = store
    logger.info("WP4 SAP mock started -- seed data loaded")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="WP4 -- SAP S/4HANA Mock",
    description=(
        "Simulates SAP S/4HANA OData interface for the Industrial IoT demo. "
        "Implements contracts C5 (OperationConfirmations), C6 (ProductionOrders), "
        "C7 (Materials), C8 (GoodsMovements)."
    ),
    version="1.0.0",
)

app.include_router(api_module.router)


if __name__ == "__main__":
    port = int(os.getenv("SAP_API_PORT", "8003"))
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
