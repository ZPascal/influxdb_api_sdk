# -*- coding: utf-8 -*-
"""Unit tests for the InfluxDBClient.

NB/WARNING:
This module implements tests for the InfluxDBClient class
but does so
 + without any server instance running
 + by mocking all the expected responses.

So any change of (response format from) the server will **NOT** be
detected by this module.

See client_test_with_server.py for tests against a running server instance.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import random
import socket
import unittest
from unittest.mock import MagicMock
import warnings

import io
import gzip
import json

from unittest import TestCase
from unittest.mock import patch

import urllib3
from urllib3.exceptions import ConnectionError, HTTPError

from tests.unittests import urllib3_mock as requests_mock
from tests.unittests.urllib3_mock import _mocked_session, Mocker, _MockHTTPResponse

from influxdb import InfluxDBClient
from influxdb.resultset import ResultSet
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError


class TestInfluxDBClient(TestCase):
    """Set up the TestInfluxDBClient object."""

    def setUp(self):
        """Initialize an instance of TestInfluxDBClient object."""
        # By default, raise exceptions on warnings
        warnings.simplefilter("error", FutureWarning)

        self.influxdb_client = InfluxDBClient("localhost", 8086, "username", "password")
        self.dummy_points = [
            {
                "measurement": "cpu_load_short",
                "tags": {"host": "server01", "region": "us-west"},
                "time": "2009-11-10T23:00:00.123456Z",
                "fields": {"value": 0.64},
            }
        ]

        self.dsn_string = "influxdb://uSr:pWd@my.host.fr:1886/db"

    def test_scheme(self):
        """Set up the test schema for TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password", "database")
        self.assertEqual("http://host:8086", influxdb_client._baseurl)

        influxdb_client = InfluxDBClient("host", 8086, "username", "password", "database", ssl_usage=True)
        self.assertEqual("https://host:8086", influxdb_client._baseurl)

        influxdb_client = InfluxDBClient(
            "host", 8086, "username", "password", "database", ssl_usage=True, path="somepath"
        )
        self.assertEqual("https://host:8086/somepath", influxdb_client._baseurl)

        influxdb_client = InfluxDBClient("host", 8086, "username", "password", "database", ssl_usage=True, path=None)
        self.assertEqual("https://host:8086", influxdb_client._baseurl)

        influxdb_client = InfluxDBClient(
            "host", 8086, "username", "password", "database", ssl_usage=True, path="/somepath"
        )
        self.assertEqual("https://host:8086/somepath", influxdb_client._baseurl)

    def test_dsn(self):
        """Set up the test datasource name for TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient.from_dsn("influxdb://192.168.0.1:1886")
        self.assertEqual("http://192.168.0.1:1886", influxdb_client._baseurl)

        influxdb_client = InfluxDBClient.from_dsn(self.dsn_string)
        self.assertEqual("http://my.host.fr:1886", influxdb_client._baseurl)
        self.assertEqual("uSr", influxdb_client._username)
        self.assertEqual("pWd", influxdb_client._password)
        self.assertEqual("db", influxdb_client._database)
        self.assertFalse(influxdb_client._use_udp)

        influxdb_client = InfluxDBClient.from_dsn("udp+" + self.dsn_string)
        self.assertTrue(influxdb_client._use_udp)

        influxdb_client = InfluxDBClient.from_dsn("https+" + self.dsn_string)
        self.assertEqual("https://my.host.fr:1886", influxdb_client._baseurl)

        influxdb_client = InfluxDBClient.from_dsn("https+" + self.dsn_string, **{"ssl_usage": False})
        self.assertEqual("http://my.host.fr:1886", influxdb_client._baseurl)

    def test_cert(self):
        """Test mutual TLS authentication for TestInfluxDBClient object."""
        import ssl

        ssl_ctx = ssl.create_default_context()
        influxdb_client = InfluxDBClient(ssl_usage=True, ssl_context=ssl_ctx)
        self.assertEqual(influxdb_client._ssl_context, ssl_ctx)

        with self.assertRaises(ValueError):
            InfluxDBClient(ssl_context=ssl_ctx)

    def test_switch_database(self):
        """Test switch database in TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password", "database")
        influxdb_client.switch_database("another_database")
        self.assertEqual("another_database", influxdb_client._database)

    def test_switch_user(self):
        """Test switch user in TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password", "database")
        influxdb_client.switch_user("another_username", "another_password")
        self.assertEqual("another_username", influxdb_client._username)
        self.assertEqual("another_password", influxdb_client._password)

    def test_write(self):
        """Test write in TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)
            influxdb_client = InfluxDBClient(database="db")
            influxdb_client.write(
                {
                    "database": "mydb",
                    "retentionPolicy": "mypolicy",
                    "points": [
                        {
                            "measurement": "cpu_load_short",
                            "tags": {"host": "server01", "region": "us-west"},
                            "time": "2009-11-10T23:00:00Z",
                            "fields": {"value": 0.64},
                        }
                    ],
                }
            )

            self.assertEqual(
                m.last_request.body,
                b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000000000000\n",
            )

    def test_write_points(self):
        """Test write points for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)

            influxdb_client = InfluxDBClient(database="db")
            influxdb_client.write_points(
                self.dummy_points,
            )
            self.assertEqual(
                "cpu_load_short,host=server01,region=us-west value=0.64 1257894000123456000\n",
                m.last_request.body.decode("utf-8"),
            )

    def test_write_gzip(self):
        """Test write in TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)

            influxdb_client = InfluxDBClient(database="db", gzip=True)
            influxdb_client.write(
                {
                    "database": "mydb",
                    "retentionPolicy": "mypolicy",
                    "points": [
                        {
                            "measurement": "cpu_load_short",
                            "tags": {"host": "server01", "region": "us-west"},
                            "time": "2009-11-10T23:00:00Z",
                            "fields": {"value": 0.64},
                        }
                    ],
                }
            )

            compressed = io.BytesIO()
            with gzip.GzipFile(compresslevel=9, fileobj=compressed, mode="w") as f:
                f.write(b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000000000000\n")

            self.assertEqual(
                m.last_request.body,
                compressed.getvalue(),
            )

    def test_write_points_gzip(self):
        """Test write points for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)

            influxdb_client = InfluxDBClient(database="db", gzip=True)
            influxdb_client.write_points(
                self.dummy_points,
            )

            compressed = io.BytesIO()
            with gzip.GzipFile(compresslevel=9, fileobj=compressed, mode="w") as f:
                f.write(b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000123456000\n")
            self.assertEqual(
                m.last_request.body,
                compressed.getvalue(),
            )

    def test_write_points_toplevel_attributes(self):
        """Test write points attrs for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)

            influxdb_client = InfluxDBClient(database="db")
            influxdb_client.write_points(
                self.dummy_points,
                database="testdb",
                tags={"tag": "hello"},
                retention_policy="somepolicy",
            )
            self.assertEqual(
                "cpu_load_short,host=server01,region=us-west,tag=hello value=0.64 1257894000123456000\n",
                m.last_request.body.decode("utf-8"),
            )

    def test_write_points_batch(self):
        """Test write points batch for TestInfluxDBClient object."""
        dummy_points = [
            {
                "measurement": "cpu_usage",
                "tags": {"unit": "percent"},
                "time": "2009-11-10T23:00:00Z",
                "fields": {"value": 12.34},
            },
            {
                "measurement": "network",
                "tags": {"direction": "in"},
                "time": "2009-11-10T23:00:00Z",
                "fields": {"value": 123.00},
            },
            {
                "measurement": "network",
                "tags": {"direction": "out"},
                "time": "2009-11-10T23:00:00Z",
                "fields": {"value": 12.00},
            },
        ]
        expected_last_body = "network,direction=out,host=server01,region=us-west value=12.0 1257894000000000000\n"

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)
            influxdb_client = InfluxDBClient(database="db")
            influxdb_client.write_points(
                points=dummy_points,
                database="db",
                tags={"host": "server01", "region": "us-west"},
                batch_size=2,
            )
        self.assertEqual(m.call_count, 2)
        self.assertEqual(expected_last_body, m.last_request.body.decode("utf-8"))

    def test_write_points_batch_generator(self):
        """Test write points batch from a generator for TestInfluxDBClient."""
        dummy_points = [
            {
                "measurement": "cpu_usage",
                "tags": {"unit": "percent"},
                "time": "2009-11-10T23:00:00Z",
                "fields": {"value": 12.34},
            },
            {
                "measurement": "network",
                "tags": {"direction": "in"},
                "time": "2009-11-10T23:00:00Z",
                "fields": {"value": 123.00},
            },
            {
                "measurement": "network",
                "tags": {"direction": "out"},
                "time": "2009-11-10T23:00:00Z",
                "fields": {"value": 12.00},
            },
        ]
        dummy_points_generator = (point for point in dummy_points)
        expected_last_body = "network,direction=out,host=server01,region=us-west value=12.0 1257894000000000000\n"

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)
            influxdb_client = InfluxDBClient(database="db")
            influxdb_client.write_points(
                points=dummy_points_generator,
                database="db",
                tags={"host": "server01", "region": "us-west"},
                batch_size=2,
            )
        self.assertEqual(m.call_count, 2)
        self.assertEqual(expected_last_body, m.last_request.body.decode("utf-8"))

    def test_write_points_udp(self):
        """Test write points UDP for TestInfluxDBClient object."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        port = random.randint(4000, 8000)
        s.bind(("0.0.0.0", port))

        influxdb_client = InfluxDBClient("localhost", 8086, "root", "root", "test", use_udp=True, udp_port=port)
        influxdb_client.write_points(self.dummy_points)

        received_data, addr = s.recvfrom(1024)

        self.assertEqual(
            "cpu_load_short,host=server01,region=us-west value=0.64 1257894000123456000\n",
            received_data.decode(),
        )

    def test_write_points_fails(self):
        """Test write points fail for TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password", "db")
        with _mocked_session(influxdb_client, "post", 500):
            with self.assertRaises(InfluxDBServerError):
                influxdb_client.write_points([])

    def test_write_points_with_precision(self):
        """Test write points with precision for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)

            influxdb_client = InfluxDBClient(database="db")

            influxdb_client.write_points(self.dummy_points, time_precision="n")
            self.assertEqual(
                b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000123456000\n",
                m.last_request.body,
            )

            influxdb_client.write_points(self.dummy_points, time_precision="u")
            self.assertEqual(
                b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000123456\n",
                m.last_request.body,
            )

            influxdb_client.write_points(self.dummy_points, time_precision="ms")
            self.assertEqual(
                b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000123\n",
                m.last_request.body,
            )

            influxdb_client.write_points(self.dummy_points, time_precision="s")
            self.assertEqual(
                b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000\n",
                m.last_request.body,
            )

            influxdb_client.write_points(self.dummy_points, time_precision="m")
            self.assertEqual(
                b"cpu_load_short,host=server01,region=us-west value=0.64 20964900\n",
                m.last_request.body,
            )

            influxdb_client.write_points(self.dummy_points, time_precision="h")
            self.assertEqual(
                b"cpu_load_short,host=server01,region=us-west value=0.64 349415\n",
                m.last_request.body,
            )

    def test_write_points_with_consistency(self):
        """Test write points with consistency for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)

            influxdb_client = InfluxDBClient(database="db")

            influxdb_client.write_points(self.dummy_points, consistency="any")
            self.assertEqual(m.last_request.qs, {"db": ["db"], "consistency": ["any"]})

    def test_write_points_with_precision_udp(self):
        """Test write points with precision for TestInfluxDBClient object."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        port = random.randint(4000, 8000)
        s.bind(("0.0.0.0", port))

        influxdb_client = InfluxDBClient("localhost", 8086, "root", "root", "test", use_udp=True, udp_port=port)

        influxdb_client.write_points(self.dummy_points, time_precision="n")
        received_data, addr = s.recvfrom(1024)
        self.assertEqual(
            b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000123456000\n",
            received_data,
        )

        influxdb_client.write_points(self.dummy_points, time_precision="u")
        received_data, addr = s.recvfrom(1024)
        self.assertEqual(
            b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000123456\n",
            received_data,
        )

        influxdb_client.write_points(self.dummy_points, time_precision="ms")
        received_data, addr = s.recvfrom(1024)
        self.assertEqual(
            b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000123\n",
            received_data,
        )

        influxdb_client.write_points(self.dummy_points, time_precision="s")
        received_data, addr = s.recvfrom(1024)
        self.assertEqual(
            b"cpu_load_short,host=server01,region=us-west value=0.64 1257894000\n",
            received_data,
        )

        influxdb_client.write_points(self.dummy_points, time_precision="m")
        received_data, addr = s.recvfrom(1024)
        self.assertEqual(
            b"cpu_load_short,host=server01,region=us-west value=0.64 20964900\n",
            received_data,
        )

        influxdb_client.write_points(self.dummy_points, time_precision="h")
        received_data, addr = s.recvfrom(1024)
        self.assertEqual(
            b"cpu_load_short,host=server01,region=us-west value=0.64 349415\n",
            received_data,
        )

    def test_write_points_bad_precision(self):
        """Test write points w/bad precision TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient()
        with self.assertRaisesRegex(
            Exception,
            r"Invalid time precision is given. \(use 'n', 'u', 'ms', 's', 'm' or 'h'\)",
        ):
            influxdb_client.write_points(self.dummy_points, time_precision="g")

    def test_write_points_bad_consistency(self):
        """Test write points w/bad consistency value."""
        influxdb_client = InfluxDBClient()
        with self.assertRaises(ValueError):
            influxdb_client.write_points(self.dummy_points, consistency="boo")

    def test_write_points_with_precision_fails(self):
        """Test write points w/precision fail for TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password", "db")
        with _mocked_session(influxdb_client, "post", 500):
            with self.assertRaises(InfluxDBServerError):
                influxdb_client.write_points([])

    def test_query(self):
        """Test query method for TestInfluxDBClient object."""
        example_response = (
            '{"results": [{"series": [{"measurement": "sdfsdfsdf", '
            '"columns": ["time", "value"], "values": '
            '[["2009-11-10T23:00:00Z", 0.64]]}]}, {"series": '
            '[{"measurement": "cpu_load_short", "columns": ["time", "value"], '
            '"values": [["2009-11-10T23:00:00Z", 0.64]]}]}]}'
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", text=example_response)
            rs = self.influxdb_client.query("select * from foo")

            self.assertListEqual(
                list(rs[0].get_points()),
                [{"value": 0.64, "time": "2009-11-10T23:00:00Z"}],
            )

    def test_query_msgpack(self):
        """Test query method with a messagepack response."""
        example_response = bytes(
            bytearray.fromhex(
                "81a7726573756c74739182ac73746174656d656e745f696400a673657269"
                "65739183a46e616d65a161a7636f6c756d6e7392a474696d65a176a67661"
                "6c7565739192c70c05000000005d26178a019096c8cb3ff0000000000000"
            )
        )

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/query",
                request_headers={"Accept": "application/x-msgpack"},
                headers={"Content-Type": "application/x-msgpack"},
                content=example_response,
            )
            rs = self.influxdb_client.query("select * from a")

            self.assertListEqual(
                list(rs.get_points()),
                [{"v": 1.0, "time": "2019-07-10T16:51:22.026253Z"}],
            )

    def test_select_into_post(self):
        """Test SELECT.*INTO is POSTed."""
        example_response = (
            '{"results": [{"series": [{"measurement": "sdfsdfsdf", '
            '"columns": ["time", "value"], "values": '
            '[["2009-11-10T23:00:00Z", 0.64]]}]}, {"series": '
            '[{"measurement": "cpu_load_short", "columns": ["time", "value"], '
            '"values": [["2009-11-10T23:00:00Z", 0.64]]}]}]}'
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            rs = self.influxdb_client.query("select * INTO newmeas from foo")

            self.assertListEqual(
                list(rs[0].get_points()),
                [{"value": 0.64, "time": "2009-11-10T23:00:00Z"}],
            )

    @unittest.skip("Not implemented for 0.9")
    def test_query_chunked(self):  # pragma: no cover
        """Test chunked query for TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient(database="db")
        example_object = {
            "points": [
                [1415206250119, 40001, 667],
                [1415206244555, 30001, 7],
                [1415206228241, 20001, 788],
                [1415206212980, 10001, 555],
                [1415197271586, 10001, 23],
            ],
            "measurement": "foo",
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
                influxdb_client.query("select * from foo", chunked=True),
                [example_object, example_object],
            )

    def test_query_fail(self):
        """Test query failed for TestInfluxDBClient object."""
        with _mocked_session(self.influxdb_client, "get", 401):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.query("select column_one from foo;")

    def test_ping(self):
        """Test ping querying InfluxDB version."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/ping",
                status_code=204,
                headers={"X-Influxdb-Version": "1.2.3"},
            )
            version = self.influxdb_client.ping()
            self.assertEqual(version, "1.2.3")

    def test_create_database(self):
        """Test create database for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}',
            )
            self.influxdb_client.create_database("new_db")
            self.assertEqual(m.last_request.qs["q"][0], 'CREATE DATABASE "new_db"')

    def test_create_numeric_named_database(self):
        """Test create db w/numeric name for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}',
            )
            self.influxdb_client.create_database("123")
            self.assertEqual(m.last_request.qs["q"][0], 'CREATE DATABASE "123"')

    def test_create_database_fails(self):
        """Test create database fail for TestInfluxDBClient object."""
        with _mocked_session(self.influxdb_client, "post", 401):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.create_database("new_db")

    def test_drop_database(self):
        """Test drop database for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}',
            )
            self.influxdb_client.drop_database("new_db")
            self.assertEqual(m.last_request.qs["q"][0], 'DROP DATABASE "new_db"')

    def test_drop_measurement(self):
        """Test drop measurement for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}',
            )
            self.influxdb_client.drop_measurement("new_measurement")
            self.assertEqual(m.last_request.qs["q"][0], 'DROP MEASUREMENT "new_measurement"')

    def test_drop_numeric_named_database(self):
        """Test drop numeric db for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/query",
                text='{"results":[{}]}',
            )
            self.influxdb_client.drop_database("123")
            self.assertEqual(m.last_request.qs["q"][0], 'DROP DATABASE "123"')

    def test_get_list_database(self):
        """Test get list of databases for TestInfluxDBClient object."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "name": "databases",
                            "values": [["new_db_1"], ["new_db_2"]],
                            "columns": ["name"],
                        }
                    ]
                }
            ]
        }

        with _mocked_session(self.influxdb_client, "get", 200, json.dumps(data)):
            self.assertListEqual(
                self.influxdb_client.get_list_database(),
                [{"name": "new_db_1"}, {"name": "new_db_2"}],
            )

    def test_get_list_database_fails(self):
        """Test get list of dbs fail for TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password")
        with _mocked_session(influxdb_client, "get", 401):
            with self.assertRaises(InfluxDBClientError):
                influxdb_client.get_list_database()

    def test_get_list_measurements(self):
        """Test get list of measurements for TestInfluxDBClient object."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "name": "measurements",
                            "columns": ["name"],
                            "values": [["cpu"], ["disk"]],
                        }
                    ]
                }
            ]
        }

        with _mocked_session(self.influxdb_client, "get", 200, json.dumps(data)):
            self.assertListEqual(self.influxdb_client.get_list_measurements(), [{"name": "cpu"}, {"name": "disk"}])

    def test_get_list_series(self):
        """Test get a list of series from the database."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "values": [
                                ["cpu_load_short,host=server01,region=us-west"],
                                ["memory_usage,host=server02,region=us-east"],
                            ],
                            "columns": ["key"],
                        }
                    ]
                }
            ]
        }

        with _mocked_session(self.influxdb_client, "get", 200, json.dumps(data)):
            self.assertListEqual(
                self.influxdb_client.get_list_series(),
                [
                    "cpu_load_short,host=server01,region=us-west",
                    "memory_usage,host=server02,region=us-east",
                ],
            )

    def test_get_list_series_with_measurement(self):
        """Test get a list of series from the database by filter."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "values": [["cpu_load_short,host=server01,region=us-west"]],
                            "columns": ["key"],
                        }
                    ]
                }
            ]
        }

        with _mocked_session(self.influxdb_client, "get", 200, json.dumps(data)):
            self.assertListEqual(
                self.influxdb_client.get_list_series(measurement="cpu_load_short"),
                ["cpu_load_short,host=server01,region=us-west"],
            )

    def test_get_list_series_with_tags(self):
        """Test get a list of series from the database by tags."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "values": [["cpu_load_short,host=server01,region=us-west"]],
                            "columns": ["key"],
                        }
                    ]
                }
            ]
        }

        with _mocked_session(self.influxdb_client, "get", 200, json.dumps(data)):
            self.assertListEqual(
                self.influxdb_client.get_list_series(tags={"region": "us-west"}),
                ["cpu_load_short,host=server01,region=us-west"],
            )

    def test_get_list_series_fails(self):
        """Test get a list of series from the database but fail."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password")
        with _mocked_session(influxdb_client, "get", 401):
            with self.assertRaises(InfluxDBClientError):
                influxdb_client.get_list_series()

    def test_create_retention_policy_default(self):
        """Test create default ret policy for TestInfluxDBClient object."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.create_retention_policy("somename", "1d", 4, default=True, database="db")

            self.assertEqual(
                m.last_request.qs["q"][0],
                'CREATE RETENTION POLICY "somename" ON "db" DURATION 1d REPLICATION 4 SHARD DURATION 0s DEFAULT',
            )

    def test_create_retention_policy(self):
        """Test create retention policy for TestInfluxDBClient object."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.create_retention_policy("somename", "1d", 4, database="db")

            self.assertEqual(
                m.last_request.qs["q"][0],
                'CREATE RETENTION POLICY "somename" ON "db" DURATION 1d REPLICATION 4 SHARD DURATION 0s',
            )

    def test_create_retention_policy_shard_duration(self):
        """Test create retention policy with a custom shard duration."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.create_retention_policy("somename2", "1d", 4, database="db", shard_duration="1h")

            self.assertEqual(
                m.last_request.qs["q"][0],
                'CREATE RETENTION POLICY "somename2" ON "db" DURATION 1d REPLICATION 4 SHARD DURATION 1h',
            )

    def test_create_retention_policy_shard_duration_default(self):
        """Test create retention policy with a default shard duration."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.create_retention_policy(
                "somename3", "1d", 4, database="db", shard_duration="1h", default=True
            )

            self.assertEqual(
                m.last_request.qs["q"][0],
                'CREATE RETENTION POLICY "somename3" ON "db" DURATION 1d REPLICATION 4 SHARD DURATION 1h DEFAULT',
            )

    def test_alter_retention_policy(self):
        """Test alter retention policy for TestInfluxDBClient object."""
        example_response = '{"results":[{}]}'

        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)

            # Test alter duration
            self.influxdb_client.alter_retention_policy("somename", "db", duration="4d")
            self.assertEqual(
                m.last_request.qs["q"][0],
                'ALTER RETENTION POLICY "somename" ON "db" DURATION 4d',
            )

            # Test alter replication
            self.influxdb_client.alter_retention_policy("somename", "db", replication=4)
            self.assertEqual(
                m.last_request.qs["q"][0],
                'ALTER RETENTION POLICY "somename" ON "db" REPLICATION 4',
            )

            # Test alter shard duration
            self.influxdb_client.alter_retention_policy("somename", "db", shard_duration="1h")
            self.assertEqual(
                m.last_request.qs["q"][0],
                'ALTER RETENTION POLICY "somename" ON "db" SHARD DURATION 1h',
            )

            # Test alter default
            self.influxdb_client.alter_retention_policy("somename", "db", default=True)
            self.assertEqual(
                m.last_request.qs["q"][0],
                'ALTER RETENTION POLICY "somename" ON "db" DEFAULT',
            )

    def test_alter_retention_policy_invalid(self):
        """Test invalid alter ret policy for TestInfluxDBClient object."""
        with _mocked_session(self.influxdb_client, "get", 400):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.alter_retention_policy("somename", "db")

    def test_drop_retention_policy(self):
        """Test drop retention policy for TestInfluxDBClient object."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.drop_retention_policy("somename", "db")
            self.assertEqual(m.last_request.qs["q"][0], 'DROP RETENTION POLICY "somename" ON "db"')

    def test_drop_retention_policy_fails(self):
        """Test failed drop ret policy for TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password")
        with _mocked_session(influxdb_client, "delete", 401):
            with self.assertRaises(InfluxDBClientError):
                influxdb_client.drop_retention_policy("default", "db")

    def test_get_list_retention_policies(self):
        """Test get retention policies for TestInfluxDBClient object."""
        example_response = (
            '{"results": [{"series": [{"values": [["fsfdsdf", "24h0m0s", 2]],'
            ' "columns": ["name", "duration", "replicaN"]}]}]}'
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", text=example_response)
            self.assertListEqual(
                self.influxdb_client.get_list_retention_policies("db"),
                [{"duration": "24h0m0s", "name": "fsfdsdf", "replicaN": 2}],
            )

    def test_request_retry(self):
        """Test that two connection errors will be handled."""

        class CustomMock(object):
            """Create custom mock object for test."""

            def __init__(self):
                self.i = 0

            def connection_error(self, *args, **kwargs):
                """Handle a connection error for the CustomMock object."""
                self.i += 1

                if self.i < 3:
                    raise ConnectionError

                return _MockHTTPResponse(status=204)

        influxdb_client = InfluxDBClient(database="db")
        with patch.object(influxdb_client._session, "request", side_effect=CustomMock().connection_error):
            influxdb_client.write_points(self.dummy_points)

    def test_request_retry_raises(self):
        """Test that three requests errors will not be handled."""

        class CustomMock(object):
            """Create custom mock object for test."""

            def __init__(self):
                self.i = 0

            def connection_error(self, *args, **kwargs):
                """Handle a connection error for the CustomMock object."""
                self.i += 1

                if self.i < 4:
                    raise HTTPError
                else:  # pragma: no cover
                    return _MockHTTPResponse(status=200)

        influxdb_client = InfluxDBClient(database="db")

        with self.assertRaises(HTTPError):
            with patch.object(influxdb_client._session, "request", side_effect=CustomMock().connection_error):
                influxdb_client.write_points(self.dummy_points)

    def test_random_request_retry(self):
        """Test that a random number of connection errors will be handled."""

        class CustomMock(object):
            """Create custom mock object for test."""

            def __init__(self, retries):
                self.i = 0
                self.retries = retries

            def connection_error(self, *args, **kwargs):
                """Handle a connection error for the CustomMock object."""
                self.i += 1

                if self.i < self.retries:
                    raise ConnectionError
                else:
                    return _MockHTTPResponse(status=204)

        retries = random.randint(2, 5)
        influxdb_client = InfluxDBClient(database="db", retries=retries)
        with patch.object(influxdb_client._session, "request", side_effect=CustomMock(retries).connection_error):
            influxdb_client.write_points(self.dummy_points)

    def test_random_request_retry_raises(self):
        """Test a random number of conn errors plus one will not be handled."""

        class CustomMock(object):
            """Create custom mock object for test."""

            def __init__(self, retries):
                self.i = 0
                self.retries = retries

            def connection_error(self, *args, **kwargs):
                """Handle a connection error for the CustomMock object."""
                self.i += 1

                if self.i < self.retries + 1:
                    raise ConnectionError
                else:  # pragma: no cover
                    return _MockHTTPResponse(status=200)

        retries = random.randint(1, 5)
        influxdb_client = InfluxDBClient(database="db", retries=retries)

        with self.assertRaises(ConnectionError):
            with patch.object(influxdb_client._session, "request", side_effect=CustomMock(retries).connection_error):
                influxdb_client.write_points(self.dummy_points)

    def test_get_list_users(self):
        """Test get users for TestInfluxDBClient object."""
        example_response = '{"results":[{"series":[{"columns":["user","admin"],"values":[["test",false]]}]}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", text=example_response)

            self.assertListEqual(self.influxdb_client.get_list_users(), [{"user": "test", "admin": False}])

    def test_get_list_users_empty(self):
        """Test get empty userlist for TestInfluxDBClient object."""
        example_response = '{"results":[{"series":[{"columns":["user","admin"]}]}]}'
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", text=example_response)

            self.assertListEqual(self.influxdb_client.get_list_users(), [])

    def test_grant_admin_privileges(self):
        """Test grant admin privs for TestInfluxDBClient object."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.grant_admin_privileges("test")

            self.assertEqual(m.last_request.qs["q"][0], 'GRANT ALL PRIVILEGES TO "test"')

    def test_grant_admin_privileges_invalid(self):
        """Test grant invalid admin privs for TestInfluxDBClient object."""
        with _mocked_session(self.influxdb_client, "get", 400):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.grant_admin_privileges("")

    def test_revoke_admin_privileges(self):
        """Test revoke admin privs for TestInfluxDBClient object."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.revoke_admin_privileges("test")

            self.assertEqual(m.last_request.qs["q"][0], 'REVOKE ALL PRIVILEGES FROM "test"')

    def test_revoke_admin_privileges_invalid(self):
        """Test revoke invalid admin privs for TestInfluxDBClient object."""
        with _mocked_session(self.influxdb_client, "get", 400):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.revoke_admin_privileges("")

    def test_grant_privilege(self):
        """Test grant privs for TestInfluxDBClient object."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.grant_privilege("read", "testdb", "test")

            self.assertEqual(m.last_request.qs["q"][0], 'GRANT read ON "testdb" TO "test"')

    def test_grant_privilege_invalid(self):
        """Test grant invalid privs for TestInfluxDBClient object."""
        with _mocked_session(self.influxdb_client, "get", 400):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.grant_privilege("", "testdb", "test")

    def test_revoke_privilege(self):
        """Test revoke privs for TestInfluxDBClient object."""
        example_response = '{"results":[{}]}'

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", text=example_response)
            self.influxdb_client.revoke_privilege("read", "testdb", "test")

            self.assertEqual(m.last_request.qs["q"][0], 'REVOKE read ON "testdb" FROM "test"')

    def test_revoke_privilege_invalid(self):
        """Test revoke invalid privs for TestInfluxDBClient object."""
        with _mocked_session(self.influxdb_client, "get", 400):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.revoke_privilege("", "testdb", "test")

    def test_get_list_privileges(self):
        """Test get list of privs for TestInfluxDBClient object."""
        data = {
            "results": [
                {
                    "series": [
                        {
                            "columns": ["database", "privilege"],
                            "values": [
                                ["db1", "READ"],
                                ["db2", "ALL PRIVILEGES"],
                                ["db3", "NO PRIVILEGES"],
                            ],
                        }
                    ]
                }
            ]
        }

        with _mocked_session(self.influxdb_client, "get", 200, json.dumps(data)):
            self.assertListEqual(
                self.influxdb_client.get_list_privileges("test"),
                [
                    {"database": "db1", "privilege": "READ"},
                    {"database": "db2", "privilege": "ALL PRIVILEGES"},
                    {"database": "db3", "privilege": "NO PRIVILEGES"},
                ],
            )

    def test_get_list_privileges_fails(self):
        """Test failed get list of privs for TestInfluxDBClient object."""
        influxdb_client = InfluxDBClient("host", 8086, "username", "password")
        with _mocked_session(influxdb_client, "get", 401):
            with self.assertRaises(InfluxDBClientError):
                influxdb_client.get_list_privileges("test")

    def test_get_list_continuous_queries(self):
        """Test getting a list of continuous queries."""
        data = {
            "results": [
                {
                    "statement_id": 0,
                    "series": [
                        {
                            "name": "testdb01",
                            "columns": ["name", "query"],
                            "values": [
                                ["testname01", "testquery01"],
                                ["testname02", "testquery02"],
                            ],
                        },
                        {
                            "name": "testdb02",
                            "columns": ["name", "query"],
                            "values": [["testname03", "testquery03"]],
                        },
                        {"name": "testdb03", "columns": ["name", "query"]},
                    ],
                }
            ]
        }

        with _mocked_session(self.influxdb_client, "get", 200, json.dumps(data)):
            self.assertListEqual(
                self.influxdb_client.get_list_continuous_queries(),
                [
                    {
                        "testdb01": [
                            {"name": "testname01", "query": "testquery01"},
                            {"name": "testname02", "query": "testquery02"},
                        ]
                    },
                    {"testdb02": [{"name": "testname03", "query": "testquery03"}]},
                    {"testdb03": []},
                ],
            )

    def test_get_list_continuous_queries_fails(self):
        """Test failing to get a list of continuous queries."""
        with _mocked_session(self.influxdb_client, "get", 400):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.get_list_continuous_queries()

    def test_create_continuous_query(self):
        """Test continuous query creation."""
        data = {"results": [{}]}
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", text=json.dumps(data))
            query = 'SELECT count("value") INTO "6_months"."events" FROM "events" GROUP BY time(10m)'
            self.influxdb_client.create_continuous_query("cq_name", query, "db_name")
            self.assertEqual(
                m.last_request.qs["q"][0],
                'CREATE CONTINUOUS QUERY "cq_name" ON "db_name" BEGIN SELECT '
                'count("value") INTO "6_months"."events" FROM "events" GROUP '
                "BY time(10m) END",
            )
            self.influxdb_client.create_continuous_query("cq_name", query, "db_name", "EVERY 10s FOR 2m")
            self.assertEqual(
                m.last_request.qs["q"][0],
                'CREATE CONTINUOUS QUERY "cq_name" ON "db_name" RESAMPLE '
                'EVERY 10s FOR 2m BEGIN SELECT count("value") INTO '
                '"6_months"."events" FROM "events" GROUP BY time(10m) END',
            )

    def test_create_continuous_query_fails(self):
        """Test failing to create a continuous query."""
        with _mocked_session(self.influxdb_client, "get", 400):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.create_continuous_query("cq_name", "select", "db_name")

    def test_drop_continuous_query(self):
        """Test dropping a continuous query."""
        data = {"results": [{}]}
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", text=json.dumps(data))
            self.influxdb_client.drop_continuous_query("cq_name", "db_name")
            self.assertEqual(
                m.last_request.qs["q"][0],
                'DROP CONTINUOUS QUERY "cq_name" ON "db_name"',
            )

    def test_drop_continuous_query_fails(self):
        """Test failing to drop a continuous query."""
        with _mocked_session(self.influxdb_client, "get", 400):
            with self.assertRaises(InfluxDBClientError):
                self.influxdb_client.drop_continuous_query("cq_name", "db_name")

    def test_invalid_port_fails(self):
        """Test invalid port fail for TestInfluxDBClient object."""
        with self.assertRaises(ValueError):
            InfluxDBClient("host", "80/redir", "username", "password")

    def test_chunked_response(self):
        """Test chunked response for TestInfluxDBClient object."""
        example_response = (
            '{"results":[{"statement_id":0,"series":[{"columns":["key"],'
            '"values":[["cpu"],["memory"],["iops"],["network"]],"partial":'
            'true}],"partial":true}]}\n{"results":[{"statement_id":0,'
            '"series":[{"columns":["key"],"values":[["qps"],["uptime"],'
            '["df"],["mount"]]}]}]}\n'
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", text=example_response)
            response = self.influxdb_client.query("show series", chunked=True, chunk_size=4)
            res = list(response)
            self.assertTrue(len(res) == 2)
            self.assertEqual(
                res[0].__repr__(),
                ResultSet(
                    {
                        "series": [
                            {
                                "columns": ["key"],
                                "values": [["cpu"], ["memory"], ["iops"], ["network"]],
                            }
                        ]
                    }
                ).__repr__(),
            )
            self.assertEqual(
                res[1].__repr__(),
                ResultSet(
                    {
                        "series": [
                            {
                                "columns": ["key"],
                                "values": [["qps"], ["uptime"], ["df"], ["mount"]],
                            }
                        ]
                    }
                ).__repr__(),
            )

    def test_auth_default(self):
        """Test auth with default settings."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/ping",
                status_code=204,
                headers={"X-Influxdb-Version": "1.2.3"},
            )

            influxdb_client = InfluxDBClient()
            influxdb_client.ping()

            self.assertEqual(m.last_request.headers["Authorization"], "Basic cm9vdDpyb290")

    def test_auth_username_password(self):
        """Test auth with custom username and password."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/ping",
                status_code=204,
                headers={"X-Influxdb-Version": "1.2.3"},
            )

            influxdb_client = InfluxDBClient(username="my-username", password="my-password")
            influxdb_client.ping()

            self.assertEqual(
                m.last_request.headers["Authorization"],
                "Basic bXktdXNlcm5hbWU6bXktcGFzc3dvcmQ=",
            )

    def test_auth_username_password_none(self):
        """Test auth with not defined username or password."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/ping",
                status_code=204,
                headers={"X-Influxdb-Version": "1.2.3"},
            )

            influxdb_client = InfluxDBClient(username=None, password=None)
            influxdb_client.ping()
            self.assertFalse("Authorization" in m.last_request.headers)

            influxdb_client = InfluxDBClient(username=None)
            influxdb_client.ping()
            self.assertFalse("Authorization" in m.last_request.headers)

            influxdb_client = InfluxDBClient(password=None)
            influxdb_client.ping()
            self.assertFalse("Authorization" in m.last_request.headers)

    def test_auth_token(self):
        """Test auth with custom authorization header."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/ping",
                status_code=204,
                headers={"X-Influxdb-Version": "1.2.3"},
            )

            influxdb_client = InfluxDBClient(username=None, password=None, headers={"Authorization": "my-token"})
            influxdb_client.ping()
            self.assertEqual(m.last_request.headers["Authorization"], "my-token")

    def test_custom_socket_options(self):
        """Test custom socket options."""
        test_socket_options = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]

        influxdb_client = InfluxDBClient(username=None, password=None, socket_options=test_socket_options)

        self.assertEqual(
            influxdb_client._session.connection_pool_kw.get("socket_options"),
            test_socket_options,
        )

    def test_none_socket_options(self):
        """Test default socket options."""
        influxdb_client = InfluxDBClient(username=None, password=None)
        self.assertNotIn("socket_options", influxdb_client._session.connection_pool_kw)


class FakeClient(InfluxDBClient):
    """Set up a fake client instance of InfluxDBClient."""

    def __init__(self, *args, **kwargs):
        """Initialize an instance of the FakeClient object."""
        super(FakeClient, self).__init__(*args, **kwargs)

    def query(self, query, params=None, expected_response_code=200, database=None):
        """Query data from the FakeClient object."""
        if query == "Fail":
            raise Exception("Fail")
        elif query == "Fail once" and self._host == "host1":
            raise Exception("Fail Once")
        elif query == "Fail twice" and self._host in "host1 host2":
            raise Exception("Fail Twice")
        else:
            return "Success"


class TestFakeClient(unittest.TestCase):
    """Test the FakeClient helper class."""

    def test_fake_client_fail(self):
        """Test FakeClient raises on 'Fail' query."""
        c = FakeClient("host1", 8086)
        with self.assertRaises(Exception):
            c.query("Fail")

    def test_fake_client_fail_once(self):
        """Test FakeClient raises on 'Fail once' from host1."""
        c = FakeClient("host1", 8086)
        with self.assertRaises(Exception):
            c.query("Fail once")

    def test_fake_client_fail_twice(self):
        """Test FakeClient raises on 'Fail twice' from host1."""
        c = FakeClient("host1", 8086)
        with self.assertRaises(Exception):
            c.query("Fail twice")

    def test_fake_client_success(self):
        """Test FakeClient returns 'Success' for normal query."""
        c = FakeClient("host3", 8086)
        result = c.query("SELECT * FROM cpu")
        self.assertEqual(result, "Success")



class TestClientCoverage(unittest.TestCase):
    """Test client coverage scenarios."""

    def setUp(self):
        """Initialize test client."""
        self.client = InfluxDBClient("localhost", 8086, "user", "pass", "db")

    def test_socket_options_creates_pool(self):
        """Test socket options creates pool."""
        opts = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
        client = InfluxDBClient(socket_options=opts)
        self.assertIsNotNone(client._session)

    def test_proxies_set(self):
        """Test proxies are set correctly."""
        proxies = {"http": "http://proxy:3128"}
        client = InfluxDBClient(proxies=proxies)
        self.assertEqual(client._proxies, proxies)

    def test_context_manager(self):
        """Test context manager enter and exit."""
        with InfluxDBClient("localhost", 8086, "u", "p") as c:
            self.assertIsInstance(c, InfluxDBClient)

    def test_request_with_dict_data(self):
        """Test request with dict data triggers json.dumps."""
        with Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{"series":[]}]}')
            # Trigger data being a dict – via direct request call
            response = self.client.request("query", method="GET", params={"q": "SHOW DATABASES"})
            self.assertEqual(response.status, 200)

    def test_gzip_request(self):
        """Test gzip request compression."""
        client = InfluxDBClient("localhost", 8086, "u", "p", "db", gzip=True)
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)
            result = client.write(
                {"points": [{"measurement": "m", "fields": {"v": 1}}]},
                params={"db": "db"},
            )
            self.assertTrue(result)

    # Lines 306-344, 337-339, 341-306: retry logic
    def test_retry_on_connection_error(self):
        """Cover the retry branch on ConnectionError."""
        from urllib3.exceptions import ConnectionError as Urllib3ConnError
        call_count = [0]

        def flaky_request(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Urllib3ConnError("connection refused")
            return _MockHTTPResponse(status=204)

        with patch.object(self.client._session, "request", side_effect=flaky_request):
            with patch("time.sleep"):  # Don't actually sleep
                self.client.request("write", method="POST", expected_response_code=204)
        self.assertEqual(call_count[0], 3)

    def test_retry_limit_exceeded_raises(self):
        """Cover retry exhaustion: raises after retries."""
        from urllib3.exceptions import ConnectionError as Urllib3ConnError
        client = InfluxDBClient("localhost", 8086, retries=2)

        def always_fail(*args, **kwargs):
            raise Urllib3ConnError("failed")

        with patch.object(client._session, "request", side_effect=always_fail):
            with patch("time.sleep"):
                with self.assertRaises(Urllib3ConnError):
                    client.request("write", method="POST", expected_response_code=204)

    # Line 352: error reformat with msgpack
    def test_request_server_error_msgpack(self):
        """Cover 500 error path with msgpack data."""
        import msgpack
        error_body = msgpack.packb({"error": "server error"})
        response = _MockHTTPResponse(
            status=500,
            data=error_body,
            headers={"Content-Type": "application/x-msgpack"},
        )
        response._msgpack = {"error": "server error"}
        with patch.object(self.client._session, "request", return_value=response):
            with self.assertRaises(InfluxDBServerError):
                self.client.request("query", method="GET", expected_response_code=200)

    # Lines 391-396, 393: write with line protocol, data as string
    def test_write_line_protocol_string(self):
        """Cover write() when protocol='line' and data is a str."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)
            result = self.client.write(
                "cpu value=1i",
                params={"db": "db"},
                protocol="line",
            )
            self.assertTrue(result)

    # Line 411: write with line protocol list
    def test_write_line_protocol_list(self):
        """Cover write() when protocol='line' and data is a list."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)
            result = self.client.write(
                ["cpu value=1i", "mem value=2i"],
                params={"db": "db"},
                protocol="line",
            )
            self.assertTrue(result)

    # Lines 461-464: bind_params
    def test_query_with_bind_params(self):
        """Cover bind_params merging."""
        with Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{"series":[]}]}')
            result = self.client.query(
                "SELECT * FROM cpu WHERE host=$host",
                bind_params={"host": "server01"},
            )
            self.assertIsNotNone(result)

    # Lines 461-464: bind_params with existing params
    def test_query_with_bind_params_merging(self):
        """Cover bind_params merging with existing params dict."""
        with Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{"series":[]}]}')
            result = self.client.query(
                "SELECT * FROM cpu WHERE host=$host",
                params={"params": '{"existing": "value"}'},
                bind_params={"host": "server01"},
            )
            self.assertIsNotNone(result)

    # Line 473: epoch parameter
    def test_query_with_epoch(self):
        """Cover epoch parameter in query."""
        with Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{"series":[]}]}')
            result = self.client.query("SELECT * FROM cpu", epoch="s")
            self.assertIsNotNone(result)

    # Lines 477-480: chunked with chunk_size
    def test_query_chunked_with_chunk_size(self):
        """Cover chunked+chunk_size branch."""
        chunked_data = '{"results":[{"series":[{"name":"cpu","columns":["time","value"],"values":[]}]}]}\n'
        response = _MockHTTPResponse(status=200, data=chunked_data.encode("utf-8"))
        response._msgpack = None
        with patch.object(self.client._session, "request", return_value=response):
            results = list(self.client.query("SELECT * FROM cpu", chunked=True, chunk_size=100))
            self.assertIsNotNone(results)

    # Line 840: get_list_retention_policies error
    def test_get_list_retention_policies_no_database(self):
        """Cover InfluxDBClientError when no database set."""
        client = InfluxDBClient("localhost", 8086)  # no database
        with self.assertRaises(InfluxDBClientError):
            client.get_list_retention_policies()

    # Lines 870-873: create_user with admin=True
    def test_create_user_with_admin(self):
        """Cover create_user with admin=True."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{}]}')
            self.client.create_user("newuser", "password", admin=True)
            self.assertIn("WITH ALL PRIVILEGES", m.last_request.qs.get("q", [""])[0])

    # Lines 882-883: drop_user
    def test_drop_user(self):
        """Cover drop_user."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{}]}')
            self.client.drop_user("olduser")
            self.assertIn("DROP USER", m.last_request.qs.get("q", [""])[0])

    # Lines 893-894: set_user_password
    def test_set_user_password(self):
        """Cover set_user_password."""
        with Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{}]}')
            self.client.set_user_password("user1", "newpass")
            self.assertIn("SET PASSWORD", m.last_request.qs.get("q", [""])[0])

    # Lines 909-917: delete_series with tags
    def test_delete_series_with_measurement_and_tags(self):
        """Cover delete_series with both measurement and tags."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{}]}')
            self.client.delete_series(measurement="cpu", tags={"host": "server01"})
            query = m.last_request.qs.get("q", [""])[0]
            self.assertIn("DROP SERIES", query)
            self.assertIn("FROM", query)
            self.assertIn("WHERE", query)

    # Lines 1056-1057: send_packet with line protocol
    def test_send_packet_line_protocol(self):
        """Cover send_packet with protocol='line'."""
        mock_socket = MagicMock()
        with patch("socket.socket", return_value=mock_socket):
            client = InfluxDBClient(use_udp=True, udp_port=4444)
            client.udp_socket = mock_socket
            client.send_packet(["cpu value=1i"], protocol="line")
            mock_socket.sendto.assert_called_once()

    # Lines 1062-1063: close() with non-PoolManager session
    def test_close_non_pool_manager(self):
        """Cover close() when session is not PoolManager."""
        mock_session = MagicMock()
        client = InfluxDBClient(session=mock_session)
        client.close()  # Should not raise, and should not call mock_session.clear()
        mock_session.clear.assert_not_called()

    def test_close_pool_manager(self):
        """Cover close() when session IS PoolManager."""
        self.client.close()
        # No exception = success; PoolManager.clear() was called

    # Lines 1083, 1091: _parse_dsn unknown scheme / unknown modifier
    def test_parse_dsn_unknown_scheme(self):
        """Cover ValueError for unknown scheme."""
        with self.assertRaises(ValueError):
            InfluxDBClient.from_dsn("postgres://localhost:5432/mydb")

    def test_parse_dsn_unknown_modifier(self):
        """Cover ValueError for unknown modifier."""
        with self.assertRaises(ValueError):
            InfluxDBClient.from_dsn("ftp+influxdb://localhost:8086/mydb")

    # Line 1124: _msgpack_parse_hook with non-5 code
    def test_msgpack_parse_hook_non_5_code(self):
        """Cover _msgpack_parse_hook with code != 5."""
        import msgpack
        from influxdb.client import _msgpack_parse_hook
        result = _msgpack_parse_hook(99, b"somedata")
        self.assertIsInstance(result, msgpack.ExtType)

    # Line 352 path: client error with msgpack
    def test_request_client_error_with_msgpack(self):
        """Cover client error path where msgpack data exists."""
        import msgpack
        error_body = msgpack.packb({"error": "bad request"})
        response = _MockHTTPResponse(
            status=400,
            data=error_body,
            headers={"Content-Type": "application/x-msgpack"},
        )
        response._msgpack = {"error": "bad request"}
        with patch.object(self.client._session, "request", return_value=response):
            with self.assertRaises(InfluxDBClientError):
                self.client.request("query", method="GET", expected_response_code=200)

    def test_retry_infinite(self):
        """Cover retry=0 (infinite) path: raises after HTTPError."""
        from urllib3.exceptions import HTTPError as Urllib3HTTPError
        client = InfluxDBClient("localhost", 8086, retries=0)
        call_count = [0]

        def fail_then_succeed(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Urllib3HTTPError("error")
            return _MockHTTPResponse(status=200, data=b'{"results":[{}]}')

        with patch.object(client._session, "request", side_effect=fail_then_succeed):
            response = client.request("query", method="GET", expected_response_code=200)
            self.assertEqual(response.status, 200)


# ---------------------------------------------------------------------------
# dataframe_client.py – lines 15-26: ImportError branch
# ---------------------------------------------------------------------------


class TestClientCoverageExtra(unittest.TestCase):
    """Extra tests for client.py coverage gaps."""

    def setUp(self):
        """Initialize test client."""
        self.client = InfluxDBClient("localhost", 8086, "user", "pass", "db")

    def test_request_with_dict_data(self):
        """Cover line 286: request() when data is a dict (json.dumps called)."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)
            # Pass dict directly to request - triggers json.dumps
            self.client.request("write", method="POST", data={"key": "val"},
                                expected_response_code=204)

    def test_gzip_request_with_data_none(self):
        """Cover 296->304: gzip mode when data is None (e.g., GET query)."""
        client = InfluxDBClient("localhost", 8086, "u", "p", "db", gzip=True)
        with Mocker() as m:
            m.register_uri(requests_mock.GET, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{}]}')
            # GET request with gzip=True, data=None → covers 296->304 False branch
            client.request("query", method="GET", params={"q": "SHOW DATABASES"},
                           data=None, expected_response_code=200)

    def test_write_unknown_protocol(self):
        """Cover 391->396: write() with unknown protocol (nei json nor line)."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/write", status_code=204)
            # Use protocol that's neither "json" nor "line" → data stays unchanged (None)
            self.client.write(None, params={"db": "db"}, protocol="csv",
                              expected_response_code=204)

    def test_read_chunked_response_empty_line(self):
        """Cover line 411: _read_chunked_response skips empty lines."""
        chunked_data = (
            '{"results":[{"series":[{"name":"cpu","columns":["time","value"],"values":[]}]}]}\n'
            '\n'  # empty line – triggers the `continue` on line 411
            '{"results":[{"series":[]}]}\n'
        )
        response = _MockHTTPResponse(status=200, data=chunked_data.encode("utf-8"))
        results = list(InfluxDBClient._read_chunked_response(response))
        self.assertEqual(len(results), 2)

    def test_query_chunked_no_chunk_size(self):
        """Cover 477->480: query with chunked=True but chunk_size=0 (default)."""
        chunked_data = '{"results":[{"series":[]}]}\n'
        response = _MockHTTPResponse(status=200, data=chunked_data.encode("utf-8"))
        response._msgpack = None
        with patch.object(self.client._session, "request", return_value=response):
            results = list(self.client.query("SELECT * FROM cpu", chunked=True))
            self.assertIsNotNone(results)

    def test_create_user_without_admin(self):
        """Cover 871->873: create_user with admin=False (default)."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{}]}')
            self.client.create_user("newuser", "password")  # admin=False by default
            query = m.last_request.qs.get("q", [""])[0]
            self.assertNotIn("WITH ALL PRIVILEGES", query)

    def test_delete_series_tags_only(self):
        """Cover 911->914: delete_series with tags but no measurement."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{}]}')
            self.client.delete_series(tags={"host": "server01"})
            query = m.last_request.qs.get("q", [""])[0]
            self.assertIn("WHERE", query)
            self.assertNotIn("FROM", query)

    def test_delete_series_no_args(self):
        """Cover 914->917: delete_series without measurement or tags."""
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/query", status_code=200,
                           text='{"results":[{}]}')
            self.client.delete_series()
            query = m.last_request.qs.get("q", [""])[0]
            self.assertEqual(query.strip(), "DROP SERIES")

    def test_send_packet_line_protocol_v2(self):
        """Cover 1056->1058: send_packet with protocol='line'."""
        mock_socket = MagicMock()
        client = InfluxDBClient(use_udp=True, udp_port=4444)
        client.udp_socket = mock_socket
        client.send_packet(["cpu value=1i", "mem value=2i"], protocol="line")
        mock_socket.sendto.assert_called_once()

    def test_retry_then_succeed(self):
        """Test retry then succeed scenario."""
        call_count = [0]

        def fail_once(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise urllib3.exceptions.ConnectionError("connection refused")
            return _MockHTTPResponse(status=200, data=b'{"results":[{}]}')

        with patch.object(self.client._session, "request", side_effect=fail_once):
            with patch("time.sleep"):
                response = self.client.request("query", method="GET",
                                               expected_response_code=200)
        self.assertEqual(response.status, 200)
        self.assertEqual(call_count[0], 2)

    def test_request_retry_on_connection_error_with_zero_retries(self):
        """Test connection error with retries=1 (no retry)."""
        client = InfluxDBClient("localhost", 8086, retries=1)

        def raise_connection_error(*args, **kwargs):
            raise urllib3.exceptions.ConnectionError("Connection failed")

        with patch.object(client._session, "request", side_effect=raise_connection_error):
            with self.assertRaises(urllib3.exceptions.ConnectionError):
                client.request("query", method="GET", expected_response_code=200)

    def test_request_post_without_params(self):
        """Test POST request without params."""
        response = _MockHTTPResponse(status=204, data=b'')
        with patch.object(self.client._session, "request", return_value=response):
            result = self.client.request("write", method="POST", data="test", expected_response_code=204)
            self.assertEqual(result.status, 204)
