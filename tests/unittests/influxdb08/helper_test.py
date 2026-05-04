# -*- coding: utf-8 -*-
"""Define set of helper functions for the dataframe."""

import warnings

from unittest import TestCase
from unittest.mock import MagicMock
from influxdb.influxdb08 import SeriesHelper, InfluxDBClient
from urllib3.exceptions import MaxRetryError


class TestSeriesHelper(TestCase):
    """Define the SeriesHelper for test."""

    @classmethod
    def setUpClass(cls):
        """Set up an instance of the TestSerisHelper object."""
        super(TestSeriesHelper, cls).setUpClass()

        TestSeriesHelper.client = InfluxDBClient("host", 8086, "username", "password", "database")

        class MySeriesHelper(SeriesHelper):
            """Define a subset SeriesHelper instance."""

            class Meta:
                """Define metadata for the TestSeriesHelper object."""

                client = TestSeriesHelper.client
                series_name = "events.stats.{server_name}"
                fields = ["time", "server_name"]
                bulk_size = 5
                autocommit = True

        TestSeriesHelper.MySeriesHelper = MySeriesHelper

    def test_auto_commit(self):
        """Test that write_points called after the right number of events."""

        class AutoCommitTest(SeriesHelper):
            """Define an instance of SeriesHelper for AutoCommit test."""

            class Meta:
                """Define metadata AutoCommitTest object."""

                series_name = "events.stats.{server_name}"
                fields = ["time", "server_name"]
                bulk_size = 5
                client = InfluxDBClient()
                autocommit = True

        fake_write_points = MagicMock()
        AutoCommitTest(server_name="us.east-1", time=159)
        AutoCommitTest._client.write_points = fake_write_points
        AutoCommitTest(server_name="us.east-1", time=158)
        AutoCommitTest(server_name="us.east-1", time=157)
        AutoCommitTest(server_name="us.east-1", time=156)
        self.assertFalse(fake_write_points.called)
        AutoCommitTest(server_name="us.east-1", time=3443)
        self.assertTrue(fake_write_points.called)

    def test_single_series_name(self):
        """Test JSON conversion when there is only one series name."""
        TestSeriesHelper.MySeriesHelper(server_name="us.east-1", time=159)
        TestSeriesHelper.MySeriesHelper(server_name="us.east-1", time=158)
        TestSeriesHelper.MySeriesHelper(server_name="us.east-1", time=157)
        TestSeriesHelper.MySeriesHelper(server_name="us.east-1", time=156)
        expectation = [
            {
                "points": [
                    [159, "us.east-1"],
                    [158, "us.east-1"],
                    [157, "us.east-1"],
                    [156, "us.east-1"],
                ],
                "name": "events.stats.us.east-1",
                "columns": ["time", "server_name"],
            }
        ]

        rcvd = TestSeriesHelper.MySeriesHelper._json_body_()
        self.assertTrue(
            all(el in expectation for el in rcvd) and all(el in rcvd for el in expectation),
            "Invalid JSON body of time series returned from _json_body_ for one series name: {0}.".format(rcvd),
        )
        TestSeriesHelper.MySeriesHelper._reset_()
        self.assertEqual(
            TestSeriesHelper.MySeriesHelper._json_body_(),
            [],
            "Resetting helper did not empty datapoints.",
        )

    def test_several_series_names(self):
        """Test JSON conversion when there is only one series name."""
        TestSeriesHelper.MySeriesHelper(server_name="us.east-1", time=159)
        TestSeriesHelper.MySeriesHelper(server_name="fr.paris-10", time=158)
        TestSeriesHelper.MySeriesHelper(server_name="lu.lux", time=157)
        TestSeriesHelper.MySeriesHelper(server_name="uk.london", time=156)
        expectation = [
            {
                "points": [[157, "lu.lux"]],
                "name": "events.stats.lu.lux",
                "columns": ["time", "server_name"],
            },
            {
                "points": [[156, "uk.london"]],
                "name": "events.stats.uk.london",
                "columns": ["time", "server_name"],
            },
            {
                "points": [[158, "fr.paris-10"]],
                "name": "events.stats.fr.paris-10",
                "columns": ["time", "server_name"],
            },
            {
                "points": [[159, "us.east-1"]],
                "name": "events.stats.us.east-1",
                "columns": ["time", "server_name"],
            },
        ]

        rcvd = TestSeriesHelper.MySeriesHelper._json_body_()
        self.assertTrue(
            all(el in expectation for el in rcvd) and all(el in rcvd for el in expectation),
            "Invalid JSON body of time series returned from _json_body_ for several series names: {0}.".format(rcvd),
        )
        TestSeriesHelper.MySeriesHelper._reset_()
        self.assertEqual(
            TestSeriesHelper.MySeriesHelper._json_body_(),
            [],
            "Resetting helper did not empty datapoints.",
        )

    def test_invalid_helpers(self):
        """Test errors in invalid helpers."""

        class MissingMeta(SeriesHelper):
            """Define SeriesHelper object for MissingMeta test."""

            pass

        class MissingClient(SeriesHelper):
            """Define SeriesHelper object for MissingClient test."""

            class Meta:
                """Define metadata for MissingClient object."""

                series_name = "events.stats.{server_name}"
                fields = ["time", "server_name"]
                autocommit = True

        class MissingSeriesName(SeriesHelper):
            """Define SeriesHelper object for MissingSeries test."""

            class Meta:
                """Define metadata for MissingSeriesName object."""

                fields = ["time", "server_name"]

        class MissingFields(SeriesHelper):
            """Define SeriesHelper for MissingFields test."""

            class Meta:
                """Define metadata for MissingFields object."""

                series_name = "events.stats.{server_name}"

        for cls in [MissingMeta, MissingClient, MissingFields, MissingSeriesName]:
            self.assertRaises(AttributeError, cls, **{"time": 159, "server_name": "us.east-1"})

    def test_warn_bulk_size_zero(self):
        """Test warning for an invalid bulk size."""

        class WarnBulkSizeZero(SeriesHelper):
            """Define SeriesHelper for WarnBulkSizeZero test."""

            class Meta:
                """Define metadata for WarnBulkSizeZero object."""

                client = TestSeriesHelper.client
                series_name = "events.stats.{server_name}"
                fields = ["time", "server_name"]
                bulk_size = 0
                autocommit = True

        with warnings.catch_warnings(record=True) as rec_warnings:
            warnings.simplefilter("always")
            # Server defined in the client is invalid, we're testing
            # the warning only.
            with self.assertRaises(MaxRetryError):
                WarnBulkSizeZero(time=159, server_name="us.east-1")

        self.assertGreaterEqual(
            len(rec_warnings),
            1,
            "{0} call should have generated one warning.Actual generated warnings: {1}".format(
                WarnBulkSizeZero, "\n".join(map(str, rec_warnings))
            ),
        )

        expected_msg = "Definition of bulk_size in WarnBulkSizeZero forced to 1, was less than 1."

        self.assertIn(
            expected_msg,
            [w.message.args[0] for w in rec_warnings],
            'Warning message did not contain "forced to 1".',
        )

    def test_warn_bulk_size_no_effect(self):
        """Test warning for a set bulk size but autocommit False."""

        class WarnBulkSizeNoEffect(SeriesHelper):
            """Define SeriesHelper for WarnBulkSizeNoEffect object."""

            class Meta:
                """Define metadata for WarnBulkSizeNoEffect object."""

                series_name = "events.stats.{server_name}"
                fields = ["time", "server_name"]
                bulk_size = 5
                autocommit = False

        with warnings.catch_warnings(record=True) as rec_warnings:
            warnings.simplefilter("always")
            WarnBulkSizeNoEffect(time=159, server_name="us.east-1")

        self.assertGreaterEqual(
            len(rec_warnings),
            1,
            "{0} call should have generated one warning.Actual generated warnings: {1}".format(
                WarnBulkSizeNoEffect, "\n".join(map(str, rec_warnings))
            ),
        )

        expected_msg = "Definition of bulk_size in WarnBulkSizeNoEffect has no affect because autocommit is false."

        self.assertIn(
            expected_msg,
            [w.message.args[0] for w in rec_warnings],
            "Warning message did not contain the expected_msg.",
        )



class TestInfluxdb08HelperCoverage(TestCase):
    def test_bulk_size_warn_forced(self):
        """Cover lines 74-75: bulk_size < 1 forced to 1."""
        from influxdb.influxdb08.helper import SeriesHelper
        from influxdb.influxdb08 import InfluxDBClient as C08

        class BulkZeroHelper(SeriesHelper):
            class Meta:
                series_name = "test.{server}"
                fields = ["server", "value"]
                bulk_size = 0
                client = C08()
                autocommit = True

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                BulkZeroHelper(server="s1", value=1)
            except Exception:
                pass
        warning_messages = [str(x.message) for x in w if issubclass(x.category, UserWarning)]
        self.assertTrue(any("forced to 1" in msg for msg in warning_messages))

    def test_no_fields_match_raises(self):
        """Cover line 99: field mismatch raises NameError."""
        from influxdb.influxdb08.helper import SeriesHelper

        class SimpleHelper(SeriesHelper):
            class Meta:
                series_name = "test.{server}"
                fields = ["server", "value"]
                autocommit = False

        with self.assertRaises(NameError):
            SimpleHelper(server="s1")  # missing 'value'

    def test_commit_with_client(self):
        """Cover line 114->116: commit passes explicit client."""
        from influxdb.influxdb08.helper import SeriesHelper

        class CommitHelper(SeriesHelper):
            class Meta:
                series_name = "test.{server}"
                fields = ["server", "value"]
                autocommit = False

        CommitHelper(server="s1", value=10)
        mock_client = MagicMock()
        mock_client.write_points.return_value = True
        result = CommitHelper.commit(client=mock_client)
        self.assertTrue(result)
        CommitHelper._reset_()

    def test_bulk_size_no_autocommit_warns(self):
        """Cover line 128: bulk_size with autocommit=False warns."""
        from influxdb.influxdb08.helper import SeriesHelper

        class NoBulkHelper(SeriesHelper):
            class Meta:
                series_name = "data.{srv}"
                fields = ["srv", "val"]
                bulk_size = 5
                autocommit = False

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            NoBulkHelper(srv="x", val=1)
        user_warnings = [str(x.message) for x in w if issubclass(x.category, UserWarning)]
        self.assertTrue(any("has no affect" in msg for msg in user_warnings))
        NoBulkHelper._reset_()


class TestInfluxdb08HelperJsonBodyUninitialized(TestCase):
    """Test influxdb08/helper.py line 128 (uninitialized _json_body_)."""

    def test_json_body_uninitialized(self):
        """Cover line 128: _json_body_ calls _reset_() when not initialized."""
        from influxdb.influxdb08.helper import SeriesHelper

        class UniqueHelper08(SeriesHelper):
            class Meta:
                series_name = "unique_08.{host}"
                fields = ["val"]
                autocommit = False

        # Initialize to set up the class
        UniqueHelper08.__initialized__ = False
        result = UniqueHelper08._json_body_()
        self.assertEqual(result, [])

