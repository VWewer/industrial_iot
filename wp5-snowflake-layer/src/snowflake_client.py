from __future__ import annotations

import logging
from typing import Any

import snowflake.connector

from .exceptions import SnowflakeConnectionError, SnowflakeQueryError

log = logging.getLogger(__name__)

_client: "SnowflakeClient | None" = None


def _svc() -> "SnowflakeClient":
    if _client is None:
        raise SnowflakeConnectionError(
            "SnowflakeClient not initialised -- call init() first"
        )
    return _client


def init(
    account: str,
    user: str,
    password: str,
    database: str,
    schema: str,
    warehouse: str,
    role: str = "SYSADMIN",
) -> "SnowflakeClient":
    global _client
    _client = SnowflakeClient(
        account=account,
        user=user,
        password=password,
        database=database,
        schema=schema,
        warehouse=warehouse,
        role=role,
    )
    _client.connect()
    return _client


class SnowflakeClient:
    def __init__(
        self,
        account: str,
        user: str,
        password: str,
        database: str,
        schema: str,
        warehouse: str,
        role: str,
    ) -> None:
        self._account = account
        self._user = user
        self._password = password
        self._database = database
        self._schema = schema
        self._warehouse = warehouse
        self._role = role
        self._conn: snowflake.connector.SnowflakeConnection | None = None

    def connect(self) -> None:
        try:
            self._conn = snowflake.connector.connect(
                account=self._account,
                user=self._user,
                password=self._password,
                database=self._database,
                schema=self._schema,
                warehouse=self._warehouse,
                role=self._role,
            )
            log.info(
                "Snowflake connected",
                extra={"account": self._account, "database": self._database},
            )
        except Exception as exc:
            raise SnowflakeConnectionError(
                f"Failed to connect to Snowflake: {exc}"
            ) from exc

    def _conn_or_raise(self) -> snowflake.connector.SnowflakeConnection:
        if self._conn is None:
            raise SnowflakeConnectionError("Not connected -- call connect() first")
        return self._conn

    def execute(self, sql: str, params: tuple | None = None) -> None:
        try:
            with self._conn_or_raise().cursor() as cur:
                cur.execute(sql, params)
        except SnowflakeConnectionError:
            raise
        except Exception as exc:
            raise SnowflakeQueryError(f"Query failed: {exc}") from exc

    def execute_many(self, sql: str, rows: list[tuple]) -> int:
        if not rows:
            return 0
        try:
            with self._conn_or_raise().cursor() as cur:
                cur.executemany(sql, rows)
            return len(rows)
        except SnowflakeConnectionError:
            raise
        except Exception as exc:
            raise SnowflakeQueryError(f"Batch insert failed: {exc}") from exc

    def fetchall(self, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
        try:
            with self._conn_or_raise().cursor() as cur:
                cur.execute(sql, params)
                if cur.description is None:
                    return []
                cols = [desc[0].lower() for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        except SnowflakeConnectionError:
            raise
        except Exception as exc:
            raise SnowflakeQueryError(f"Query failed: {exc}") from exc

    def fetchone(self, sql: str, params: tuple | None = None) -> dict[str, Any] | None:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def run_script(self, sql: str) -> None:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                self.execute(stmt)

    def is_connected(self) -> bool:
        if self._conn is None:
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            log.info("Snowflake connection closed")
