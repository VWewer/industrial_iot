"""Custom exceptions for WP3 Mendix mock."""
from __future__ import annotations


class OrderNotFoundError(Exception):
    """Raised when an order_id does not exist in the local store or SAP."""


class InvalidStateTransitionError(Exception):
    """Raised when an order transition is attempted from the wrong current status.

    Carries the order_id, current status, and attempted target status for context.
    """

    def __init__(self, order_id: str, current: str, attempted: str) -> None:
        super().__init__(
            f"Order {order_id}: cannot transition from '{current}' to '{attempted}'"
        )
        self.order_id = order_id
        self.current = current
        self.attempted = attempted


class SAPClientError(Exception):
    """Raised when a call to the WP4 SAP mock returns an error or times out."""


class SimaticClientError(Exception):
    """Raised when a call to the WP2 SIMATIC mock returns an error or times out."""


class WP1ClientError(Exception):
    """Raised when a call to the WP1 control API returns an error or times out."""


class WP5ClientError(Exception):
    """Raised when the WP5 MES event webhook call fails."""
