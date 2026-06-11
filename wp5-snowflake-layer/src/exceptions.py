class SnowflakeConnectionError(Exception):
    """Raised when the Snowflake connection cannot be established."""


class SnowflakeQueryError(Exception):
    """Raised when a Snowflake query or batch insert fails."""


class MQTTConnectionError(Exception):
    """Raised when the MQTT broker cannot be reached on startup."""


class IngestionError(Exception):
    """Raised when payload validation or Bronze insertion fails."""


class SAPPullError(Exception):
    """Raised when the scheduled SAP reference data pull fails."""
