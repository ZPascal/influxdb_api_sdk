# -*- coding: utf-8 -*-
"""Integration tests for InfluxDB user management.

These tests run without HTTP auth enabled (INFLUXDB_HTTP_AUTH_ENABLED=false),
which is the default Docker Compose setup. The tests still verify that the
management API calls succeed (user objects are created/dropped in InfluxDB's
internal metadata store even without auth enforcement).
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import uuid

import pytest

from tests.integrationtests.conftest import make_client, unique_db_name


@pytest.mark.integration
class TestUserManagement(unittest.TestCase):
    """Test user CRUD and privilege management against a live InfluxDB instance."""

    def setUp(self):
        """Set up a client and an isolated database for privilege tests."""
        self.client = make_client()
        self.db_name = unique_db_name()
        self.client.create_database(self.db_name)

    def tearDown(self):
        """Drop the test database and close the client."""
        self.client.drop_database(self.db_name)
        self.client.close()

    def _unique_user(self):
        return f"test_user_{uuid.uuid4().hex[:8]}"

    def test_create_and_drop_user(self):
        """A created user should appear in the list and vanish after drop."""
        username = self._unique_user()
        self.client.create_user(username, "secret123")

        users = [u["user"] for u in self.client.get_list_users()]
        self.assertIn(username, users)

        self.client.drop_user(username)
        users_after = [u["user"] for u in self.client.get_list_users()]
        self.assertNotIn(username, users_after)

    def test_get_list_users(self):
        """get_list_users() should return a list."""
        result = self.client.get_list_users()
        self.assertIsInstance(result, list)

    def test_create_admin_user(self):
        """A user created with admin=True should have admin flag set."""
        username = self._unique_user()
        self.client.create_user(username, "admin_pass", admin=True)
        try:
            users = {u["user"]: u for u in self.client.get_list_users()}
            self.assertIn(username, users)
            self.assertTrue(users[username]["admin"])
        finally:
            self.client.drop_user(username)

    def test_grant_and_revoke_privilege(self):
        """grant_privilege() and revoke_privilege() should not raise exceptions."""
        username = self._unique_user()
        self.client.create_user(username, "pw123")
        try:
            self.client.grant_privilege("READ", self.db_name, username)
            self.client.revoke_privilege("READ", self.db_name, username)
        finally:
            self.client.drop_user(username)

    def test_grant_and_revoke_admin_privileges(self):
        """grant_admin_privileges() / revoke_admin_privileges() should toggle the admin flag."""
        username = self._unique_user()
        self.client.create_user(username, "pw123")
        try:
            self.client.grant_admin_privileges(username)
            users = {u["user"]: u for u in self.client.get_list_users()}
            self.assertTrue(users[username]["admin"])

            self.client.revoke_admin_privileges(username)
            users = {u["user"]: u for u in self.client.get_list_users()}
            self.assertFalse(users[username]["admin"])
        finally:
            self.client.drop_user(username)

    def test_set_user_password(self):
        """set_user_password() should execute without raising an exception."""
        username = self._unique_user()
        self.client.create_user(username, "initial_pw")
        try:
            self.client.set_user_password(username, "new_pw")
        finally:
            self.client.drop_user(username)
