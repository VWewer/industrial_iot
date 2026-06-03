"""
wp4-sap-mock/src/exceptions.py

Custom exceptions for WP4 SAP mock.
"""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist in the data store."""
    pass


class InvalidStatusTransitionError(Exception):
    """Raised when an order status transition is not permitted by the state machine."""
    pass


class ValidationError(Exception):
    """Raised when a request payload fails validation."""
    pass


class AlreadyConfirmedError(Exception):
    """Raised when a confirmation is posted for an already-confirmed order."""
    pass
