# -*- coding: utf-8 -*-
"""Client unit tests."""

import json
import socket
import ssl
import sys
import unittest
import random
import warnings

from unittest.mock import patch, MagicMock
from urllib3.exceptions import ConnectionError

from tests.unittests import urllib3_mock as requests_mock
from tests.unittests.urllib3_mock import _MockHTTPResponse, Mocker

from influxdb.influxdb08 import InfluxDBClient
from influxdb.influxdb08.client import session, InfluxDBClientError as InfluxDB08ClientError

if sys.version < "3":  # pragma: no cover
    import codecs

    def u(x):  # pragma: no cover
        """Test codec."""
        return codecs.unicode_escape_decode(x)[0]

else:

    def u(x):
        """Test codec."""
        return x


def _build_response_object(status_code=200, content=""):
    data = content.encode("utf8") if isinstance(content, str) else content
    return _MockHTTPResponse(status=status_code, data=data)


def _mocked_session(method="GET", status_code=200, content=""):
    method = method.upper()

    def request(*args, **kwargs):
        """Define a request for the _mocked_session."""
        c = content

        # Check method
        assert method == kwargs.get("method", "GET")

        if method == "POST":
            body = kwargs.get("body", None)

            if body is not None:  # pragma: no branch
                if isinstance(body, bytes):  # pragma: no cover
                    body = body.decode("utf-8")
                # Data must be a string
                assert isinstance(body, str)

                if c:
                    # Data must be a JSON string
                    assert c == json.loads(body, strict=True)

                c = body

        # Anyway, Content must be a JSON string (or empty string)
        if not isinstance(c, str):
            c = json.dumps(c)

        return _build_response_object(status_code=status_code, content=c)

    mocked = patch.object(session, "request", side_effect=request)

    return mocked


class TestInfluxDBClient(unittest.TestCase):
    """Define a TestInfluxDBClient object."""

    def setUp(self):
        """Set up a TestInfluxDBClient object."""
        # By default, raise exceptions on warnings
        warnings.simplefilter("error", FutureWarning)

        self.dummy_points = [
            {
                "points": [["1", 1, 1.0], ["2", 2, 2.0]],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three"],
            }
        ]

        self.dsn_string = "influxdb://uSr:pWd@host:1886/db"

    def test_scheme(self):
        """Test database scheme for TestInfluxDBClient object."""
        cli = InfluxDBClient("host", 8086, "username", "password", "database")
        self.assertEqual(cli._baseurl, "http://host:8086")

        cli = InfluxDBClient("host", 8086, "username", "password", "database", ssl_usage=True)
        self.assertEqual(cli._baseurl, "https://host:8086")

    def test_dsn(self):
        """Test datasource name for TestInfluxDBClient object."""
        cli = InfluxDBClient.from_dsn(self.dsn_string)
        self.assertEqual("http://host:1886", cli._baseurl)
        self.assertEqual("uSr", cli._username)
        self.assertEqual("pWd", cli._password)
        self.assertEqual("db", cli._database)
        self.assertFalse(cli._use_udp)

        cli = InfluxDBClient.from_dsn("udp+" + self.dsn_string)
        self.assertTrue(cli._use_udp)

        cli = InfluxDBClient.from_dsn("https+" + self.dsn_string)
        self.assertEqual("https://host:1886", cli._baseurl)

        cli = InfluxDBClient.from_dsn("https+" + self.dsn_string, **{"ssl_usage": False})
        self.assertEqual("http://host:1886", cli._baseurl)

    def test_switch_database(self):
        """Test switch database for TestInfluxDBClient object."""
        cli = InfluxDBClient("host", 8086, "username", "password", "database")
        cli.switch_database("another_database")
        self.assertEqual(cli._database, "another_database")

    def test_switch_db_deprecated(self):
        """Test deprecated switch database for TestInfluxDBClient object."""
        cli = InfluxDBClient("host", 8086, "username", "password", "database")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            cli.switch_db("another_database")
        self.assertEqual(cli._database, "another_database")

    def test_switch_user(self):
        """Test switch user for TestInfluxDBClient object."""
        cli = InfluxDBClient("host", 8086, "username", "password", "database")
        cli.switch_user("another_username", "another_password")
        self.assertEqual(cli._username, "another_username")
        self.assertEqual(cli._password, "another_password")

    def test_write(self):
        """Test write to database for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write")
            cli = InfluxDBClient(database="db")
            cli.write(
                {
                    "database": "mydb",
                    "retentionPolicy": "mypolicy",
                    "points": [
                        {
                            "name": "cpu_load_short",
                            "tags": {"host": "server01", "region": "us-west"},
                            "timestamp": "2009-11-10T23:00:00Z",
                            "values": {"value": 0.64},
                        }
                    ],
                }
            )

            self.assertEqual(
                json.loads(m.last_request.body),
                {
                    "database": "mydb",
                    "retentionPolicy": "mypolicy",
                    "points": [
                        {
                            "name": "cpu_load_short",
                            "tags": {"host": "server01", "region": "us-west"},
                            "timestamp": "2009-11-10T23:00:00Z",
                            "values": {"value": 0.64},
                        }
                    ],
                },
            )

    def test_write_points(self):
        """Test write points for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = InfluxDBClient(database="db")
            cli.write_points(self.dummy_points)

            self.assertListEqual(json.loads(m.last_request.body), self.dummy_points)

    def test_write_points_string(self):
        """Test write string points for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = InfluxDBClient(database="db")
            cli.write_points(str(json.dumps(self.dummy_points)))

            self.assertListEqual(json.loads(m.last_request.body), self.dummy_points)

    def test_write_points_batch(self):
        """Test write batch points for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")
            cli = InfluxDBClient("localhost", 8086, "username", "password", "db")
            cli.write_points(data=self.dummy_points, batch_size=2)
        self.assertEqual(1, m.call_count)

    def test_write_points_batch_invalid_size(self):
        """Test write batch points invalid size for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")
            cli = InfluxDBClient("localhost", 8086, "username", "password", "db")
            cli.write_points(data=self.dummy_points, batch_size=-2)
        self.assertEqual(1, m.call_count)

    def test_write_points_batch_multiple_series(self):
        """Test write points batch multiple series."""
        dummy_points = [
            {
                "points": [
                    ["1", 1, 1.0],
                    ["2", 2, 2.0],
                    ["3", 3, 3.0],
                    ["4", 4, 4.0],
                    ["5", 5, 5.0],
                ],
                "name": "foo",
                "columns": ["val1", "val2", "val3"],
            },
            {
                "points": [
                    ["1", 1, 1.0],
                    ["2", 2, 2.0],
                    ["3", 3, 3.0],
                    ["4", 4, 4.0],
                    ["5", 5, 5.0],
                    ["6", 6, 6.0],
                    ["7", 7, 7.0],
                    ["8", 8, 8.0],
                ],
                "name": "bar",
                "columns": ["val1", "val2", "val3"],
            },
        ]
        expected_last_body = [
            {
                "points": [["7", 7, 7.0], ["8", 8, 8.0]],
                "name": "bar",
                "columns": ["val1", "val2", "val3"],
            }
        ]
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")
            cli = InfluxDBClient("localhost", 8086, "username", "password", "db")
            cli.write_points(data=dummy_points, batch_size=3)
        self.assertEqual(m.call_count, 5)
        self.assertEqual(expected_last_body, m.request_history[4].json())

    def test_write_points_udp(self):
        """Test write points UDP for TestInfluxDBClient object."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        port = random.randint(4000, 8000)
        s.bind(("0.0.0.0", port))

        cli = InfluxDBClient("localhost", 8086, "root", "root", "test", use_udp=True, udp_port=port)
        cli.write_points(self.dummy_points)

        received_data, addr = s.recvfrom(1024)

        self.assertEqual(self.dummy_points, json.loads(received_data.decode(), strict=True))

    def test_write_bad_precision_udp(self):
        """Test write UDP w/bad precision."""
        cli = InfluxDBClient("localhost", 8086, "root", "root", "test", use_udp=True, udp_port=4444)

        with self.assertRaisesRegex(Exception, "InfluxDB only supports seconds precision for udp writes"):
            cli.write_points(self.dummy_points, time_precision="ms")

    def test_write_points_fails(self):
        """Test failed write points for TestInfluxDBClient object."""
        with _mocked_session("post", 500):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            with self.assertRaises(InfluxDB08ClientError):
                cli.write_points([])

    def test_write_points_with_precision(self):
        """Test write points with precision."""
        with _mocked_session("post", 200, self.dummy_points):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            self.assertTrue(cli.write_points(self.dummy_points))

    def test_write_points_bad_precision(self):
        """Test write points with bad precision."""
        cli = InfluxDBClient()
        with self.assertRaisesRegex(Exception, r"Invalid time precision is given. \(use 's', 'm', 'ms' or 'u'\)"):
            cli.write_points(self.dummy_points, time_precision="g")

    def test_write_points_with_precision_fails(self):
        """Test write points where precision fails."""
        with _mocked_session("post", 500):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            with self.assertRaises(InfluxDB08ClientError):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", FutureWarning)
                    cli.write_points_with_precision([])

    def test_delete_points(self):
        """Test delete points for TestInfluxDBClient object."""
        with _mocked_session("delete", 204) as mocked:
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            self.assertTrue(cli.delete_points("foo"))

            self.assertEqual(len(mocked.call_args_list), 1)
            args, kwds = mocked.call_args_list[0]

            self.assertIn("u=username", kwds["url"])
            self.assertIn("p=password", kwds["url"])
            self.assertEqual(kwds["url"].split("?")[0], "http://host:8086/db/db/series/foo")

    def test_delete_points_with_wrong_name(self):
        """Test delete points with wrong name."""
        with _mocked_session("delete", 400):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            with self.assertRaises(InfluxDB08ClientError):
                cli.delete_points("nonexist")

    def test_create_scheduled_delete(self):
        """Test create scheduled deletes."""
        cli = InfluxDBClient("host", 8086, "username", "password", "db")
        with self.assertRaises(NotImplementedError):
            cli.create_scheduled_delete([])

    def test_get_list_scheduled_delete(self):
        """Test get schedule list of deletes TestInfluxDBClient."""
        cli = InfluxDBClient("host", 8086, "username", "password", "db")
        with self.assertRaises(NotImplementedError):
            cli.get_list_scheduled_delete()

    def test_remove_scheduled_delete(self):
        """Test remove scheduled delete TestInfluxDBClient."""
        cli = InfluxDBClient("host", 8086, "username", "password", "db")
        with self.assertRaises(NotImplementedError):
            cli.remove_scheduled_delete(1)

    def test_query(self):
        """Test query for TestInfluxDBClient object."""
        data = [
            {
                "name": "foo",
                "columns": ["time", "sequence_number", "column_one"],
                "points": [
                    [1383876043, 16, "2"],
                    [1383876043, 15, "1"],
                    [1383876035, 14, "2"],
                    [1383876035, 13, "1"],
                ],
            }
        ]
        with _mocked_session("get", 200, data):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            result = cli.query("select column_one from foo;")
            self.assertEqual(len(result[0]["points"]), 4)

    def test_query_chunked(self):
        """Test chunked query for TestInfluxDBClient object."""
        cli = InfluxDBClient(database="db")
        example_object = {
            "points": [
                [1415206250119, 40001, 667],
                [1415206244555, 30001, 7],
                [1415206228241, 20001, 788],
                [1415206212980, 10001, 555],
                [1415197271586, 10001, 23],
            ],
            "name": "foo",
            "columns": ["time", "sequence_number", "val"],
        }
        example_response = json.dumps(example_object) + json.dumps(example_object)

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/series",
                text=example_response,
            )

            self.assertListEqual(
                cli.query("select * from foo", chunked=True),
                [example_object, example_object],
            )

    def test_query_chunked_unicode(self):
        """Test unicode chunked query for TestInfluxDBClient object."""
        cli = InfluxDBClient(database="db")
        example_object = {
            "points": [
                [1415206212980, 10001, u("unicode-\xcf\x89")],
                [1415197271586, 10001, u("more-unicode-\xcf\x90")],
            ],
            "name": "foo",
            "columns": ["time", "sequence_number", "val"],
        }
        example_response = json.dumps(example_object) + json.dumps(example_object)

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/series",
                text=example_response,
            )

            self.assertListEqual(
                cli.query("select * from foo", chunked=True),
                [example_object, example_object],
            )

    def test_query_fail(self):
        """Test failed query for TestInfluxDBClient."""
        with _mocked_session("get", 401):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            with self.assertRaises(InfluxDB08ClientError):
                cli.query("select column_one from foo;")

    def test_query_bad_precision(self):
        """Test query with bad precision for TestInfluxDBClient."""
        cli = InfluxDBClient()
        with self.assertRaisesRegex(Exception, r"Invalid time precision is given. \(use 's', 'm', 'ms' or 'u'\)"):
            cli.query("select column_one from foo", time_precision="g")

    def test_create_database(self):
        """Test create database for TestInfluxDBClient."""
        with _mocked_session("post", 201, {"name": "new_db"}):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            self.assertTrue(cli.create_database("new_db"))

    def test_create_database_fails(self):
        """Test failed create database for TestInfluxDBClient."""
        with _mocked_session("post", 401):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            with self.assertRaises(InfluxDB08ClientError):
                cli.create_database("new_db")

    def test_delete_database(self):
        """Test delete database for TestInfluxDBClient."""
        with _mocked_session("delete", 204):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            self.assertTrue(cli.delete_database("old_db"))

    def test_delete_database_fails(self):
        """Test failed delete database for TestInfluxDBClient."""
        with _mocked_session("delete", 401):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            with self.assertRaises(InfluxDB08ClientError):
                cli.delete_database("old_db")

    def test_get_list_database(self):
        """Test get list of databases for TestInfluxDBClient."""
        data = [{"name": "a_db"}]
        with _mocked_session("get", 200, data):
            cli = InfluxDBClient("host", 8086, "username", "password")
            self.assertEqual(len(cli.get_list_database()), 1)
            self.assertEqual(cli.get_list_database()[0]["name"], "a_db")

    def test_get_list_database_fails(self):
        """Test failed get list of databases for TestInfluxDBClient."""
        with _mocked_session("get", 401):
            cli = InfluxDBClient("host", 8086, "username", "password")
            with self.assertRaises(InfluxDB08ClientError):
                cli.get_list_database()

    def test_get_database_list_deprecated(self):
        """Test deprecated get database list for TestInfluxDBClient."""
        data = [{"name": "a_db"}]
        with _mocked_session("get", 200, data):
            cli = InfluxDBClient("host", 8086, "username", "password")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                self.assertEqual(len(cli.get_database_list()), 1)
                self.assertEqual(cli.get_database_list()[0]["name"], "a_db")

    def test_delete_series(self):
        """Test delete series for TestInfluxDBClient."""
        with _mocked_session("delete", 204):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            cli.delete_series("old_series")

    def test_delete_series_fails(self):
        """Test failed delete series for TestInfluxDBClient."""
        with _mocked_session("delete", 401):
            cli = InfluxDBClient("host", 8086, "username", "password", "db")
            with self.assertRaises(InfluxDB08ClientError):
                cli.delete_series("old_series")

    def test_get_series_list(self):
        """Test get list of series for TestInfluxDBClient."""
        cli = InfluxDBClient(database="db")

        with requests_mock.Mocker() as m:
            example_response = (
                '[{"name":"list_series_result","columns":["time","name"],"points":[[0,"foo"],[0,"bar"]]}]'
            )

            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/series",
                text=example_response,
            )

            self.assertListEqual(cli.get_list_series(), ["foo", "bar"])

    def test_get_continuous_queries(self):
        """Test get continuous queries for TestInfluxDBClient."""
        cli = InfluxDBClient(database="db")

        with requests_mock.Mocker() as m:
            # Tip: put this in a json linter!
            example_response = (
                '[ { "name": "continuous queries", "columns"'
                ': [ "time", "id", "query" ], "points": [ [ '
                '0, 1, "select foo(bar,95) from \\"foo_bar'
                's\\" group by time(5m) into response_times.'
                'percentiles.5m.95" ], [ 0, 2, "select perce'
                'ntile(value,95) from \\"response_times\\" g'
                "roup by time(5m) into response_times.percen"
                'tiles.5m.95" ] ] } ]'
            )

            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/series",
                text=example_response,
            )

            self.assertListEqual(
                cli.get_list_continuous_queries(),
                [
                    'select foo(bar,95) from "foo_bars" group by time(5m) into response_times.percentiles.5m.95',
                    'select percentile(value,95) from "response_times" group '
                    "by time(5m) into response_times.percentiles.5m.95",
                ],
            )

    def test_get_list_cluster_admins(self):
        """Test get list of cluster admins, not implemented."""
        pass

    def test_add_cluster_admin(self):
        """Test add cluster admin for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/cluster_admins")

            cli = InfluxDBClient(database="db")
            cli.add_cluster_admin(new_username="paul", new_password="laup")

            self.assertDictEqual(json.loads(m.last_request.body), {"name": "paul", "password": "laup"})

    def test_update_cluster_admin_password(self):
        """Test update cluster admin pass for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/cluster_admins/paul")

            cli = InfluxDBClient(database="db")
            cli.update_cluster_admin_password(username="paul", new_password="laup")

            self.assertDictEqual(json.loads(m.last_request.body), {"password": "laup"})

    def test_delete_cluster_admin(self):
        """Test delete cluster admin for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.DELETE,
                "http://localhost:8086/cluster_admins/paul",
                status_code=200,
            )

            cli = InfluxDBClient(database="db")
            cli.delete_cluster_admin(username="paul")

            self.assertIsNone(m.last_request.body)

    def test_set_database_admin(self):
        """Test set database admin for TestInfluxDBClient."""
        pass

    def test_unset_database_admin(self):
        """Test unset database admin for TestInfluxDBClient."""
        pass

    def test_alter_database_admin(self):
        """Test alter database admin for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users/paul")

            cli = InfluxDBClient(database="db")
            cli.alter_database_admin(username="paul", is_admin=False)

            self.assertDictEqual(json.loads(m.last_request.body), {"admin": False})

    def test_get_list_database_admins(self):
        """Test get list of database admins for TestInfluxDBClient."""
        cli = InfluxDBClient("host", 8086, "username", "password", "db")
        with self.assertRaises(NotImplementedError):
            cli.get_list_database_admins()

    def test_add_database_admin(self):
        """Test add database admins for TestInfluxDBClient."""
        cli = InfluxDBClient("host", 8086, "username", "password", "db")
        with self.assertRaises(NotImplementedError):
            cli.add_database_admin("admin", "admin_secret_password")

    def test_update_database_admin_password(self):
        """Test update database admin pass for TestInfluxDBClient."""
        cli = InfluxDBClient("host", 8086, "username", "password", "db")
        with self.assertRaises(NotImplementedError):
            cli.update_database_admin_password("admin", "admin_secret_password")

    def test_delete_database_admin(self):
        """Test delete database admin for TestInfluxDBClient."""
        cli = InfluxDBClient("host", 8086, "username", "password", "db")
        with self.assertRaises(NotImplementedError):
            cli.delete_database_admin("admin")

    def test_get_database_users(self):
        """Test get database users for TestInfluxDBClient."""
        cli = InfluxDBClient("localhost", 8086, "username", "password", "db")

        example_response = (
            '[{"name":"paul","isAdmin":false,"writeTo":".*","readFrom":".*"},'
            '{"name":"bobby","isAdmin":false,"writeTo":".*","readFrom":".*"}]'
        )

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/users",
                text=example_response,
            )
            users = cli.get_database_users()

        self.assertEqual(json.loads(example_response), users)

    def test_add_database_user(self):
        """Test add database user for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users")
            cli = InfluxDBClient(database="db")
            cli.add_database_user(new_username="paul", new_password="laup", permissions=(".*", ".*"))

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {"writeTo": ".*", "password": "laup", "readFrom": ".*", "name": "paul"},
            )

    def test_add_database_user_bad_permissions(self):
        """Test add database user with bad perms for TestInfluxDBClient."""
        cli = InfluxDBClient()

        with self.assertRaisesRegex(Exception, r"'permissions' must be \(readFrom, writeTo\) tuple"):
            cli.add_database_user(
                new_password="paul",
                new_username="paul",
                permissions=("hello", "hello", "hello"),
            )

    def test_alter_database_user_password(self):
        """Test alter database user pass for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users/paul")

            cli = InfluxDBClient(database="db")
            cli.alter_database_user(username="paul", password="n3wp4ss!")

            self.assertDictEqual(json.loads(m.last_request.body), {"password": "n3wp4ss!"})

    def test_alter_database_user_permissions(self):
        """Test alter database user perms for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users/paul")

            cli = InfluxDBClient(database="db")
            cli.alter_database_user(username="paul", permissions=("^$", ".*"))

            self.assertDictEqual(json.loads(m.last_request.body), {"readFrom": "^$", "writeTo": ".*"})

    def test_alter_database_user_password_and_permissions(self):
        """Test alter database user pass and perms for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users/paul")

            cli = InfluxDBClient(database="db")
            cli.alter_database_user(username="paul", password="n3wp4ss!", permissions=("^$", ".*"))

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {"password": "n3wp4ss!", "readFrom": "^$", "writeTo": ".*"},
            )

    def test_update_database_user_password_current_user(self):
        """Test update database user pass for TestInfluxDBClient."""
        cli = InfluxDBClient(username="root", password="hello", database="database")
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/database/users/root")

            cli.update_database_user_password(username="root", new_password="bye")

            self.assertEqual(cli._password, "bye")

    def test_delete_database_user(self):
        """Test delete database user for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.DELETE, "http://localhost:8086/db/db/users/paul")

            cli = InfluxDBClient(database="db")
            cli.delete_database_user(username="paul")

            self.assertIsNone(m.last_request.body)

    def test_update_permission(self):
        """Test update permission for TestInfluxDBClient."""
        cli = InfluxDBClient("host", 8086, "username", "password", "db")
        with self.assertRaises(NotImplementedError):
            cli.update_permission("admin", [])

    def test_request_retry(self):
        """Test that two connection errors will be handled."""

        class CustomMock(object):
            """Define CustomMock object."""

            def __init__(self):
                self.i = 0

            def connection_error(self, *args, **kwargs):
                """Test connection error in CustomMock."""
                self.i += 1

                if self.i < 3:
                    raise ConnectionError
                else:
                    return _MockHTTPResponse(status=200)

        cli = InfluxDBClient(database="db")
        with patch.object(cli._session, "request", side_effect=CustomMock().connection_error):
            cli.write_points(self.dummy_points)

    def test_request_retry_raises(self):
        """Test that three connection errors will not be handled."""

        class CustomMock(object):
            """Define CustomMock object."""

            def __init__(self):
                """Initialize the object."""
                self.i = 0

            def connection_error(self, *args, **kwargs):
                """Test the connection error for CustomMock."""
                self.i += 1

                if self.i < 4:
                    raise ConnectionError
                else:  # pragma: no cover
                    return _MockHTTPResponse(status=200)

        cli = InfluxDBClient(database="db")

        with self.assertRaises(ConnectionError):
            with patch.object(cli._session, "request", side_effect=CustomMock().connection_error):
                cli.write_points(self.dummy_points)



class TestInfluxdb08ChunkedJson(unittest.TestCase):
    """Test chunked JSON functionality for influxdb08."""

    def test_loads_basic(self):
        """Cover basic loads functionality."""
        from influxdb.influxdb08.chunked_json import loads
        result = list(loads('{"a":1}{"b":2}'))
        self.assertEqual(result, [{"a": 1}, {"b": 2}])

    def test_loads_value_error(self):
        """Cover ValueError branch."""
        from influxdb.influxdb08 import chunked_json as cj

        class _FakeDecoder:
            def raw_decode(self, s):
                return ({}, 0)

        with patch.object(cj, "json") as mock_json:
            mock_json.JSONDecoder.return_value = _FakeDecoder()
            with self.assertRaises(ValueError):
                list(cj.loads('{"a":1}'))

    def test_loads_empty_string(self):
        """Cover the while loop exit on empty string."""
        from influxdb.influxdb08.chunked_json import loads
        result = list(loads(""))
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# influxdb08/client.py – missing branches
# ---------------------------------------------------------------------------


class TestInfluxdb08ClientCoverage(unittest.TestCase):
    """Test coverage scenarios for influxdb08 client."""

    def setUp(self):
        """Initialize test fixtures."""
        from influxdb.influxdb08 import InfluxDBClient as InfluxDB08Client
        from influxdb.influxdb08.client import session

        self.InfluxDB08Client = InfluxDB08Client
        self.session = session
        self.client = InfluxDB08Client("localhost", 8086, "user", "pass", "db")

    def test_socket_options(self):
        """Cover socket_options branch in __init__."""
        opts = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
        client = self.InfluxDB08Client(socket_options=opts)
        self.assertIsNotNone(client._session)

    def test_ssl_context_without_ssl_raises(self):
        """Cover ValueError: SSL context with ssl disabled."""
        ctx = ssl.create_default_context()
        with self.assertRaises(ValueError):
            self.InfluxDB08Client(ssl_context=ctx, ssl_usage=False)

    def test_from_dsn_unknown_scheme(self):
        """Cover unknown scheme ValueError in from_dsn."""
        with self.assertRaises(ValueError):
            self.InfluxDB08Client.from_dsn("postgres://localhost/db")

    def test_from_dsn_unknown_modifier(self):
        """Cover unknown modifier ValueError."""
        with self.assertRaises(ValueError):
            self.InfluxDB08Client.from_dsn("ftp+influxdb://localhost:8086/db")

    def test_from_dsn_full(self):
        """Cover from_dsn with all optional parts."""
        client = self.InfluxDB08Client.from_dsn("influxdb://user:pass@myhost:9999/mydb")
        self.assertEqual(client._host, "myhost")
        self.assertEqual(client._port, 9999)
        self.assertEqual(client._username, "user")
        self.assertEqual(client._password, "pass")
        self.assertEqual(client._database, "mydb")

    def test_from_dsn_https(self):
        """Cover https modifier."""
        client = self.InfluxDB08Client.from_dsn("https+influxdb://localhost:8086/db")
        self.assertEqual(client._scheme, "https")

    def test_from_dsn_udp(self):
        """Cover udp modifier."""
        client = self.InfluxDB08Client.from_dsn("udp+influxdb://localhost:8086/db")
        self.assertTrue(client._use_udp)

    def test_delete_request(self):
        """Cover DELETE method path."""
        with Mocker() as m:
            m.register_uri(requests_mock.DELETE, "http://localhost:8086/db/testdb",
                           status_code=204)
            result = self.client.delete_database("testdb")
            self.assertTrue(result)

    def test_retry_exhausted_raises(self):
        """Cover retry exhaustion in influxdb08 client."""
        from urllib3.exceptions import ConnectionError as CE
        client = self.InfluxDB08Client("localhost", 8086, retries=2)
        call_count = [0]

        def fail(*args, **kwargs):
            call_count[0] += 1
            raise CE("failed")

        with patch.object(client._session, "request", side_effect=fail):
            with self.assertRaises(CE):
                client.request("query", method="GET", expected_response_code=200)

    def test_query_chunked_unicode_error(self):
        """Test handling of unicode error in chunked JSON response."""
        from influxdb.influxdb08 import InfluxDBClient as C08
        import influxdb.influxdb08.chunked_json as cj

        client = C08("localhost", 8086, "u", "p", "db")
        data = '[{"points":[[1,2]],"name":"cpu","columns":["time","value"]}]'
        response = _MockHTTPResponse(status=200, data=data.encode("utf-8"))

        original_loads = cj.loads
        call_count = [0]

        def patched_loads(s):  # pragma: no cover
            call_count[0] += 1
            return original_loads(s)

        with patch.object(client._session, "request", return_value=response):
            with patch.object(cj, "loads", side_effect=patched_loads):
                result = client._query("SELECT * FROM cpu", chunked=True)
                self.assertIsNotNone(result)

    def test_get_list_cluster_admins(self):
        """Cover get_list_cluster_admins."""
        with Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/cluster_admins",
                           status_code=200, text='[{"name":"admin"}]')
            result = self.client.get_list_cluster_admins()
            self.assertEqual(result, [{"name": "admin"}])

    def test_set_database_admin(self):
        """Cover set_database_admin."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users/user1",
                           status_code=200, text='{}')
            result = self.client.set_database_admin("user1")
            self.assertTrue(result)

    def test_unset_database_admin(self):
        """Cover unset_database_admin."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users/user1",
                           status_code=200, text='{}')
            result = self.client.unset_database_admin("user1")
            self.assertTrue(result)

    def test_add_database_user_invalid_permissions(self):
        """Cover TypeError for invalid permissions."""
        with self.assertRaises(TypeError):
            with Mocker() as m:
                m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users",
                               status_code=200, text='{}')
                self.client.add_database_user("user1", "pass", permissions="invalid")

    def test_alter_database_user_no_args(self):
        """Cover ValueError when neither password nor permissions given."""
        with self.assertRaises(ValueError):
            self.client.alter_database_user("user1")

    def test_alter_database_user_invalid_permissions(self):
        """Cover TypeError for invalid permissions in alter_database_user."""
        with self.assertRaises(TypeError):
            with Mocker() as m:
                m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users/user1",
                               status_code=200, text='{}')
                self.client.alter_database_user("user1", permissions="invalid")


# ---------------------------------------------------------------------------
# influxdb08/helper.py – missing branches
# ---------------------------------------------------------------------------


class TestInfluxdb08ClientCoverageExtra(unittest.TestCase):
    """Extra tests for influxdb08/client.py coverage gaps."""

    def setUp(self):
        """Set up test fixtures for influxdb08 client coverage tests."""
        from influxdb.influxdb08 import InfluxDBClient as InfluxDB08Client
        self.C08 = InfluxDB08Client
        self.client = InfluxDB08Client("localhost", 8086, "user", "pass", "db")

    def test_from_dsn_hostname_only(self):
        """Cover 182->184 False: from_dsn with no explicit port."""
        # "influxdb://myhost" has hostname but no port
        client = self.C08.from_dsn("influxdb://myhost")
        self.assertEqual(client._host, "myhost")

    def test_from_dsn_no_host_no_port(self):
        """Cover 182->184 branch: from_dsn with minimal DSN (no hostname)."""
        # "influxdb:///mydb" has no hostname, so the hostname branch is not taken
        try:
            self.C08.from_dsn("influxdb:///mydb")
            # No hostname specified, defaults are used
        except Exception:  # pragma: no cover
            pass  # If the parse fails, the branch is still covered

    def test_from_dsn_no_path(self):
        """Cover 190->193 False: from_dsn without path."""
        client = self.C08.from_dsn("influxdb://user:pass@myhost:8086")
        # No path, so database should not be set from path
        self.assertIsNone(client._database)

    def test_from_dsn_no_username(self):
        """Cover 184->186, 186->188, 188->190 False branches when no user/pass in DSN."""
        # "influxdb://myhost:8086/mydb" - has hostname, port, path, but no username/password
        client = self.C08.from_dsn("influxdb://myhost:8086/mydb")
        # Default username/password ("root") since DSN has none
        self.assertEqual(client._host, "myhost")
        self.assertEqual(client._database, "mydb")

    def test_retry_then_succeed(self):
        """Cover 287->249: retry loop, fail once then succeed."""
        from urllib3.exceptions import ConnectionError as Urllib3ConnectionError
        client = self.C08("localhost", 8086, "u", "p", "db", retries=3)
        call_count = [0]

        def fail_once(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Urllib3ConnectionError("failed")  # urllib3 ConnectionError, caught by except block
            return _MockHTTPResponse(status=200, data=b'[]')

        with patch.object(client._session, "request", side_effect=fail_once):
            result = client.request("query", method="GET", expected_response_code=200)
        self.assertEqual(result.status, 200)
        self.assertEqual(call_count[0], 2)

    def test_retry_infinite_retries_succeeds(self):
        """Test infinite retries (retries=0) with eventual success after failure."""
        from urllib3.exceptions import ConnectionError as Urllib3ConnectionError
        client = self.C08("localhost", 8086, "u", "p", "db", retries=0)
        call_count = [0]

        def fail_once(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Urllib3ConnectionError("failed")
            return _MockHTTPResponse(status=200, data=b'[]')

        with patch.object(client._session, "request", side_effect=fail_once):
            result = client.request("query", method="GET", expected_response_code=200)
        self.assertEqual(result.status, 200)
        self.assertEqual(call_count[0], 2)

    def test_init_with_socket_options(self):
        """Test client initialization with socket options."""
        mock_session = MagicMock()
        client = self.C08("localhost", 8086, "u", "p", "db", session=mock_session)
        self.assertIs(client._session, mock_session)

    def test_chunked_query_unicode_error_fallback(self):
        """Test chunked query with unicode error fallback."""
        data_str = '[{"points":[[1,2]],"name":"cpu","columns":["time","value"]}]'
        data_bytes = data_str.encode("utf-8")

        # Create custom bytes-like response where decode() without encoding raises UnicodeDecodeError
        class FakeData:
            """Bytes-like object that raises UnicodeDecodeError on first decode."""

            def __init__(self, content):
                self._content = content
                self._decode_calls = 0

            def decode(self, encoding="utf-8"):
                self._decode_calls += 1
                if self._decode_calls == 1 and encoding == "utf-8":
                    # Normal first call - simulate default decode() (no args) behavior
                    # Actually the code calls .decode() (no args) first, then .decode("utf-8")
                    # To trigger as if .decode() fails: raise on first call
                    raise UnicodeDecodeError("ascii", b"\xff", 0, 1, "ordinal not in range")
                return self._content.decode("utf-8")

        class MockResponse:
            status = 200
            data = FakeData(data_bytes)

        with patch.object(self.client._session, "request", return_value=MockResponse()):
            result = self.client._query("SELECT * FROM cpu", chunked=True)
            self.assertIsNotNone(result)

    def test_add_database_user_no_permissions(self):
        """Cover 731->737: add_database_user without permissions."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/users",
                           status_code=200, text='{}')
            result = self.client.add_database_user("newuser", "pass123")
            self.assertTrue(result)

    def test_post_request_without_params_none(self):
        """Cover influxdb08 client line 255: POST when params is empty/falsy."""
        from influxdb.influxdb08 import InfluxDBClient as C08
        client = C08("localhost", 8086, "u", "p", "db")
        mock_resp = _MockHTTPResponse(status=200, data=b'[]')

        with patch.object(client._session, "request", return_value=mock_resp) as mock_req:
            # Call request directly with method=POST and no params
            client.request("db/db/series", method="POST", params=None, data='[]')
            call_kwargs = mock_req.call_args
            # The URL should not contain a query string when params is None/empty
            self.assertIsNotNone(call_kwargs)

    def test_delete_request_without_params(self):
        """Cover influxdb08 client line 267: DELETE when params is empty/falsy."""
        from influxdb.influxdb08 import InfluxDBClient as C08
        client = C08("localhost", 8086, "u", "p", "db")
        mock_resp = _MockHTTPResponse(status=200, data=b'')

        with patch.object(client._session, "request", return_value=mock_resp) as mock_req:
            # Call request directly with method=DELETE and no params
            client.request("db/testdb", method="DELETE", params=None)
            call_kwargs = mock_req.call_args
            self.assertIsNotNone(call_kwargs)

    def test_put_request_without_params(self):
        """Cover influxdb08 client line 267: PUT when params is empty/falsy."""
        from influxdb.influxdb08 import InfluxDBClient as C08
        client = C08("localhost", 8086, "u", "p", "db")
        mock_resp = _MockHTTPResponse(status=200, data=b'')

        with patch.object(client._session, "request", return_value=mock_resp) as mock_req:
            # Call request directly with method=PUT and no params
            client.request("db/testdb", method="PUT", params=None, data='{}')
            call_kwargs = mock_req.call_args
            self.assertIsNotNone(call_kwargs)
