# -*- coding: utf-8 -*-
"""Integration tests for InfluxDBClient core functionality."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import unittest

import pytest

from influxdb import InfluxDBClient
from tests.integrationtests.conftest import make_client, unique_db_name


@pytest.mark.integration
class TestPing(unittest.TestCase):
    """Test basic connectivity to a live InfluxDB instance."""

    def setUp(self):
        """Set up a client for each test."""
        self.client = make_client()

    def tearDown(self):
        """Close the client after each test."""
        self.client.close()

    def test_ping_returns_version(self):
        """ping() should return a non-empty version string."""
        version = self.client.ping()
        self.assertIsNotNone(version)
        self.assertIsInstance(version, str)
        self.assertGreater(len(version), 0)


@pytest.mark.integration
class TestWriteAndQuery(unittest.TestCase):
    """Test writing data points and querying them back."""

    def setUp(self):
        """Create a fresh isolated database for every test."""
        self.client = make_client()
        self.db_name = unique_db_name()
        self.client.create_database(self.db_name)
        self.client.switch_database(self.db_name)

    def tearDown(self):
        """Drop the test database and close the client."""
        self.client.drop_database(self.db_name)
        self.client.close()

    def test_write_and_query_json_points(self):
        """Written JSON points should be queryable immediately."""
        points = [
            {
                "measurement": "temperature",
                "tags": {"location": "office", "sensor": "A"},
                "fields": {"value": 22.5},
            },
            {
                "measurement": "temperature",
                "tags": {"location": "office", "sensor": "B"},
                "fields": {"value": 23.1},
            },
        ]
        self.assertTrue(self.client.write_points(points))

        time.sleep(0.5)

        rs = self.client.query("SELECT * FROM temperature")
        rows = list(rs.get_points("temperature"))
        self.assertEqual(len(rows), 2)
        values = {r["sensor"]: r["value"] for r in rows}
        self.assertAlmostEqual(values["A"], 22.5, places=3)
        self.assertAlmostEqual(values["B"], 23.1, places=3)

    def test_write_line_protocol(self):
        """A single point written via the client should be queryable."""
        self.assertTrue(
            self.client.write_points(
                [{"measurement": "cpu_load", "tags": {"host": "server01"}, "fields": {"value": 0.75}}]
            )
        )

        time.sleep(0.5)
        rs = self.client.query("SELECT value FROM cpu_load WHERE host='server01'")
        rows = list(rs.get_points("cpu_load"))
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["value"], 0.75, places=3)

    def test_write_multiple_measurements(self):
        """Points for different measurements should land in separate series."""
        points = [
            {"measurement": "mem", "fields": {"used_percent": 45.2}},
            {"measurement": "disk", "fields": {"used_percent": 60.8}},
        ]
        self.assertTrue(self.client.write_points(points))

        time.sleep(0.5)
        self.assertEqual(len(list(self.client.query("SELECT * FROM mem").get_points("mem"))), 1)
        self.assertEqual(len(list(self.client.query("SELECT * FROM disk").get_points("disk"))), 1)

    def test_query_with_epoch_parameter(self):
        """When epoch='s' the time column should be an integer (Unix seconds)."""
        self.client.write_points([{"measurement": "events", "fields": {"count": 1}}])
        time.sleep(0.5)

        rs = self.client.query("SELECT * FROM events", epoch="s")
        rows = list(rs.get_points("events"))
        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0]["time"], int)

    def test_write_batch_size(self):
        """write_points with batch_size should write all points correctly.

        Each point gets a unique 'idx' tag so InfluxDB does not deduplicate
        points that arrive with the same server-assigned nanosecond timestamp.
        """
        points = [
            {"measurement": "batch_metric", "tags": {"idx": str(i)}, "fields": {"val": float(i)}}
            for i in range(25)
        ]
        self.assertTrue(self.client.write_points(points, batch_size=10))

        time.sleep(0.5)
        rs = self.client.query("SELECT count(val) FROM batch_metric")
        rows = list(rs.get_points("batch_metric"))
        self.assertEqual(rows[0]["count"], 25)

    def test_gzip_client(self):
        """A client with gzip=True should be able to write data."""
        gz_client = make_client(database=self.db_name, gzip=True)
        try:
            result = gz_client.write_points(
                [{"measurement": "gz_metric", "fields": {"value": 1.0}}]
            )
            self.assertTrue(result)
        finally:
            gz_client.close()

    def test_from_dsn(self):
        """InfluxDBClient.from_dsn() should produce a working client."""
        host = self.client._host
        port = self.client._port
        dsn = f"influxdb://root:root@{host}:{port}/dsn_test_db"
        c = InfluxDBClient.from_dsn(dsn, timeout=10)
        try:
            self.assertIsNotNone(c.ping())
        finally:
            c.close()

