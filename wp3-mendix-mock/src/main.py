"""Entry point for WP3 -- wires services and starts FastAPI."""
from __future__ import annotations

import logging
import os

import uvicorn
from dotenv import load_dotenv

from .api import app, init_app
from .order_service import OrderService
from .sap_client import SAPClient
from .simatic_client import SimaticClient
from .wp1_client import WP1Client
from .wp5_client import WP5Client

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


def main() -> None:
    api_port = int(os.getenv("MENDIX_API_PORT", "8002"))
    sap_url = os.getenv("SAP_API_URL", "http://localhost:8003")
    simatic_url = os.getenv("SIMATIC_API_URL", "http://localhost:8001")
    wp1_url = os.getenv("WP1_CONTROL_API_URL", "http://localhost:8080")
    wp5_url = os.getenv("WP5_WEBHOOK_URL", "http://localhost:8005/events")
    oven_id = os.getenv("OVEN_ID", "oven-01")

    log.info(
        "WP3 starting",
        extra={
            "api_port": api_port,
            "sap_url": sap_url,
            "simatic_url": simatic_url,
        },
    )

    init_app(
        order_service=OrderService(),
        sap_client=SAPClient(sap_url),
        simatic_client=SimaticClient(simatic_url),
        wp1_client=WP1Client(wp1_url),
        wp5_client=WP5Client(wp5_url),
        oven_id=oven_id,
    )

    uvicorn.run(app, host="0.0.0.0", port=api_port, log_level="warning")


if __name__ == "__main__":
    main()
