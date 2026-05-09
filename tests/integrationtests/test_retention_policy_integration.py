# -*- coding: utf-8 -*-
"""Integration tests for InfluxDB retention policy management."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import pytest

from tests.integrationtests.conftest import make_client, unique_db_name


@pytest.mark.integration
class TestRetentionPolicies(unittest.TestCase):
    """Test retention policy CRUD operations against a live InfluxDB instance."""

    def setUp(self):
        """Create a client and an isolated database for every test."""
        self.client = make_client()
        self.db_name = unique_db_name()
        self.client.create_database(self.db_name)
        self.client.switch_database(self.db_name)

    def tearDown(self):
        """Drop the test database and close the client."""
        self.client.drop_database(self.db_name)
        self.client.close()

    def test_create_retention_policy(self):
        """A newly created retention policy should appear in the list."""
        self.client.create_retention_policy(
            name="short_rp",
            duration="1h",
            replication=1,
            database=self.db_name,
        )
        names = [p["name"] for p in self.client.get_list_retention_policies(database=self.db_name)]
        self.assertIn("short_rp", names)

    def test_get_list_retention_policies(self):
        """Every database should at least have the default autogen policy."""
        policies = self.client.get_list_retention_policies(database=self.db_name)
        self.assertIsInstance(policies, list)
        names = [p["name"] for p in policies]
        self.assertIn("autogen", names)

    def test_alter_retention_policy(self):
        """alter_retention_policy() should change the duration of an existing policy."""
        self.client.create_retention_policy(
            name="mutable_rp",
            duration="1h",
            replication=1,
            database=self.db_name,
        )
        self.client.alter_retention_policy(
            name="mutable_rp",
            duration="2h",
            replication=1,
            database=self.db_name,
        )
        policies = {
            p["name"]: p
            for p in self.client.get_list_retention_policies(database=self.db_name)
        }
        self.assertIn("mutable_rp", policies)
        self.assertEqual(policies["mutable_rp"]["duration"], "2h0m0s")

    def test_drop_retention_policy(self):
        """A dropped retention policy should no longer appear in the list."""
        self.client.create_retention_policy(
            name="temp_rp",
            duration="1h",
            replication=1,
            database=self.db_name,
        )
        self.client.drop_retention_policy(name="temp_rp", database=self.db_name)
        names = [p["name"] for p in self.client.get_list_retention_policies(database=self.db_name)]
        self.assertNotIn("temp_rp", names)
