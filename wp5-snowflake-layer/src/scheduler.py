from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)


class TransformScheduler:
    def __init__(
        self,
        sap_puller,
        silver_fn: Callable[[], None],
        gold_fn: Callable[[], None],
        sap_interval_s: int = 60,
        transform_interval_s: int = 30,
    ) -> None:
        self._sap_puller = sap_puller
        self._silver_fn = silver_fn
        self._gold_fn = gold_fn
        self._sap_interval_s = sap_interval_s
        self._transform_interval_s = transform_interval_s
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        self._scheduler.add_job(
            self._run_sap_pull,
            trigger=IntervalTrigger(seconds=self._sap_interval_s),
            id="sap_pull",
            name="SAP reference data pull",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._run_transforms,
            trigger=IntervalTrigger(seconds=self._transform_interval_s),
            id="transforms",
            name="Silver and Gold transforms",
            replace_existing=True,
        )
        self._scheduler.start()
        log.info(
            "Scheduler started",
            extra={
                "sap_interval_s": self._sap_interval_s,
                "transform_interval_s": self._transform_interval_s,
            },
        )

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")

    def _run_sap_pull(self) -> None:
        try:
            self._sap_puller.pull()
        except Exception as exc:
            log.error("SAP pull job failed: %s", exc)

    def _run_transforms(self) -> None:
        try:
            self._silver_fn()
            self._gold_fn()
        except Exception as exc:
            log.error("Transform job failed: %s", exc)
