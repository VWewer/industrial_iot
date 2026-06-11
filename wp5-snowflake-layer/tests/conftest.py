from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import src.snowflake_client as sf_module


@pytest.fixture
def mock_sf():
    mock = MagicMock()
    mock.is_connected.return_value = True
    mock.fetchall.return_value = []
    mock.fetchone.return_value = None
    mock.execute_many.return_value = 0
    sf_module._client = mock
    yield mock
    sf_module._client = None
