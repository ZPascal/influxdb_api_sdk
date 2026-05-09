# -*- coding: utf-8 -*-
"""Integration tests for InfluxDB database management APIs."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import unittest
import uuid

import pytest

from tests.integrationtests.conftest import make_client, unique_db_name


@pytest.mark.integration
class TestDatabaseManagement(unittest.TestCase):
    """Test database CRUD operations against a live InfluxDB instance."""

    def setUp(self):
        """Set up a client for each test."""
        self.client = make_client()

    def tearDown(self):
        """Close the client after each test."""
        self.client.close()

    def test_create_and_drop_database(self):
        """A created database should appear in the list and vanish after drop."""
        db_name = f"test_create_{uuid.uuid4().hex[:8]}"
        self.client.create_database(db_name)

        db_names = [d["name"] for d in self.client.get_list_database()]
        self.assertIn(db_name, db_names)

        self.client.drop_database(db_name)
        db_names_after = [d["name"] for d in self.client.get_list_database()]
        self.assertNotIn(db_name, db_names_after)

    def test_get_list_database(self):
        """get_list_database() should return a list that contains a database we create."""
        db_name = f"test_list_{uuid.uuid4().hex[:8]}"
        self.client.create_database(db_name)
        try:
            result = self.client.get_list_database()
            self.assertIsInstance(result, list)
            names = [d["name"] for d in result]
            self.assertIn(db_name, names)
        finally:
            self.client.drop_database(db_name)

    def test_get_list_measurements(self):
        """Written measurements should appear in get_list_measurements()."""
        db_name = unique_db_name()
        self.client.create_database(db_name)
        self.client.switch_database(db_name)
        try:
            self.client.write_points([
                {"measurement": "sensors", "fields": {"value": 1.0}},
                {"measurement": "actuators", "fields": {"value": 2.0}},
            ])
            time.sleep(0.5)

            names = [m["name"] for m in self.client.get_list_measurements()]
            self.assertIn("sensors", names)
            self.assertIn("actuators", names)
        finally:
            self.client.drop_database(db_name)

    def test_get_list_series(self):
        """Written series should appear in get_list_series()."""
        db_name = unique_db_name()
        self.client.create_database(db_name)
        self.client.switch_database(db_name)
        try:
            self.client.write_points([
                {"measurement": "env", "tags": {"room": "kitchen"}, "fields": {"temp": 21.0}},
                {"measurement": "env", "tags": {"room": "living"}, "fields": {"temp": 20.0}},
            ])
            time.sleep(0.5)

            series = self.client.get_list_series()
            self.assertGreaterEqual(len(series), 2)
        finally:
            self.client.drop_database(db_name)

    def test_drop_measurement(self):
        """After drop_measurement() no data should be returned for that measurement."""
        db_name = unique_db_name()
        self.client.create_database(db_name)
        self.client.switch_database(db_name)
        try:
            self.client.write_points([{"measurement": "to_drop", "fields": {"value": 1.0}}])
            time.sleep(0.5)

            self.client.drop_measurement("to_drop")
            time.sleep(0.5)

            rows = list(self.client.query("SELECT * FROM to_drop").get_points("to_drop"))
            self.assertEqual(len(rows), 0)
        finally:
            self.client.drop_database(db_name)

    def test_delete_series(self):
        """delete_series() with a tag filter should only remove the matching series."""
        db_name = unique_db_name()
        self.client.create_database(db_name)
        self.client.switch_database(db_name)
        try:
            self.client.write_points([
                {"measurement": "metrics", "tags": {"host": "A"}, "fields": {"val": 1.0}},
                {"measurement": "metrics", "tags": {"host": "B"}, "fields": {"val": 2.0}},
            ])
            time.sleep(0.5)

            self.client.delete_series(measurement="metrics", tags={"host": "A"})
            time.sleep(0.5)

            rows = list(self.client.query("SELECT * FROM metrics").get_points("metrics"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["host"], "B")
        finally:
            self.client.drop_database(db_name)
