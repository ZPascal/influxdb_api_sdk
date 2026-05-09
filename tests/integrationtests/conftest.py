# -*- coding: utf-8 -*-
"""Shared helpers for integration tests.

Because the tests use unittest.TestCase (matching the unit-test style) pytest
fixtures cannot be injected into test methods. Instead, this module exposes
helper functions that test classes call from setUp/tearDown.
"""

import os
import uuid

from influxdb import InfluxDBClient


def make_client(**kwargs):
    """Return an InfluxDBClient configured from environment variables.

    Environment variables (with defaults):
        INFLUXDB_HOST     – localhost
        INFLUXDB_PORT     – 8086
        INFLUXDB_USER     – root
        INFLUXDB_PASSWORD – root
    """
    return InfluxDBClient(
        host=os.environ.get("INFLUXDB_HOST", "localhost"),
        port=int(os.environ.get("INFLUXDB_PORT", "8086")),
        username=os.environ.get("INFLUXDB_USER", "root"),
        password=os.environ.get("INFLUXDB_PASSWORD", "root"),
        timeout=10,
        **kwargs,
    )


def unique_db_name():
    """Return a unique database name safe for parallel test runs."""
    return f"integration_test_{uuid.uuid4().hex[:8]}"
