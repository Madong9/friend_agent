from __future__ import annotations

import json
import logging

import httpx
import pytest
from starlette.requests import Request

from backend.app.main import cloudbase_data_error_handler
from backend.app.repositories import CloudBaseDataError


@pytest.mark.asyncio
async def test_cloudbase_error_boundary_returns_sanitized_retryable_503(caplog):
    secret = "server-only-value-must-not-leak"
    cause = httpx.ConnectTimeout("provider request included " + secret)
    error = CloudBaseDataError("get", 401, "provider detail included " + secret)
    error.__cause__ = cause
    request = Request({"type": "http", "method": "GET", "path": "/users/me"})

    with caplog.at_level(logging.ERROR, logger="backend.app.main"):
        response = await cloudbase_data_error_handler(request, error)

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "detail": "data service is temporarily unavailable; please retry later"
    }
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.operation == "get"
    assert record.upstream_status_code == 401
    assert record.exception_type == "CloudBaseDataError"
    assert record.cause_type == "ConnectTimeout"
    assert secret not in caplog.text
    assert secret not in response.body.decode()
