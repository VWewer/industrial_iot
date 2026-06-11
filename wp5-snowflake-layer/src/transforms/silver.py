from __future__ import annotations

import logging
import os

from ..snowflake_client import _svc

log = logging.getLogger(__name__)

_SQL_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "sql", "silver_transforms.sql")


def run_silver(sql_dir: str | None = None) -> None:
    path = os.path.join(sql_dir, "silver_transforms.sql") if sql_dir else _SQL_FILE
    with open(path) as f:
        sql = f.read()
    _run_statements(sql)
    log.info("Silver transforms complete")


def _run_statements(sql: str) -> None:
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            _svc().execute(stmt)
