# -*- coding: utf-8 -*-
"""Unit tests for misc module."""

from datetime import timedelta

import copy
import json
import unittest
import warnings
from unittest.mock import patch

from tests.unittests import skip_if_pypy, using_pypy
from tests.unittests import urllib3_mock as requests_mock

from .client_test import _mocked_session
from ..urllib3_mock import Mocker

if not using_pypy:  # pragma: no branch
    import pandas as pd
    from pandas._testing import assert_frame_equal
    from influxdb.influxdb08 import DataFrameClient


@skip_if_pypy
class TestDataFrameClient(unittest.TestCase):
    """Define the DataFramClient test object."""

    def setUp(self):
        """Set up an instance of TestDataFrameClient object."""
        # By default, raise exceptions on warnings
        warnings.simplefilter("error", FutureWarning)

    def test_write_points_from_dataframe(self):
        """Test write points from dataframe."""
        now = pd.Timestamp("1970-01-01 00:00+00:00")
        dataframe = pd.DataFrame(
            data=[["1", 1, 1.0], ["2", 2, 2.0]],
            index=[now, now + timedelta(hours=1)],
            columns=["column_one", "column_two", "column_three"],
        )
        points = [
            {
                "points": [["1", 1, 1.0, 0], ["2", 2, 2.0, 3600]],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three", "time"],
            }
        ]

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database="db")
            cli.write_points({"foo": dataframe})

            self.assertListEqual(json.loads(m.last_request.body), points)

    def test_write_points_from_dataframe_with_float_nan(self):
        """Test write points from dataframe with NaN float."""
        now = pd.Timestamp("1970-01-01 00:00+00:00")
        dataframe = pd.DataFrame(
            data=[[1, float("NaN"), 1.0], [2, 2, 2.0]],
            index=[now, now + timedelta(hours=1)],
            columns=["column_one", "column_two", "column_three"],
        )
        points = [
            {
                "points": [[1, None, 1.0, 0], [2, 2, 2.0, 3600]],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three", "time"],
            }
        ]

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database="db")
            cli.write_points({"foo": dataframe})

            self.assertListEqual(json.loads(m.last_request.body), points)

    def test_write_points_from_dataframe_in_batches(self):
        """Test write points from dataframe in batches."""
        now = pd.Timestamp("1970-01-01 00:00+00:00")
        dataframe = pd.DataFrame(
            data=[["1", 1, 1.0], ["2", 2, 2.0]],
            index=[now, now + timedelta(hours=1)],
            columns=["column_one", "column_two", "column_three"],
        )
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database="db")
            self.assertTrue(cli.write_points({"foo": dataframe}, batch_size=1))

    def test_write_points_from_dataframe_with_numeric_column_names(self):
        """Test write points from dataframe with numeric columns."""
        now = pd.Timestamp("1970-01-01 00:00+00:00")
        # df with numeric column names
        dataframe = pd.DataFrame(data=[["1", 1, 1.0], ["2", 2, 2.0]], index=[now, now + timedelta(hours=1)])
        points = [
            {
                "points": [["1", 1, 1.0, 0], ["2", 2, 2.0, 3600]],
                "name": "foo",
                "columns": ["0", "1", "2", "time"],
            }
        ]

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database="db")
            cli.write_points({"foo": dataframe})

            self.assertListEqual(json.loads(m.last_request.body), points)

    def test_write_points_from_dataframe_with_period_index(self):
        """Test write points from dataframe with period index."""
        dataframe = pd.DataFrame(
            data=[["1", 1, 1.0], ["2", 2, 2.0]],
            index=[pd.Period("1970-01-01"), pd.Period("1970-01-02")],
            columns=["column_one", "column_two", "column_three"],
        )
        points = [
            {
                "points": [["1", 1, 1.0, 0], ["2", 2, 2.0, 86400]],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three", "time"],
            }
        ]

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database="db")
            cli.write_points({"foo": dataframe})

            self.assertListEqual(json.loads(m.last_request.body), points)

    def test_write_points_from_dataframe_with_time_precision(self):
        """Test write points from dataframe with time precision."""
        now = pd.Timestamp("1970-01-01 00:00+00:00")
        dataframe = pd.DataFrame(
            data=[["1", 1, 1.0], ["2", 2, 2.0]],
            index=[now, now + timedelta(hours=1)],
            columns=["column_one", "column_two", "column_three"],
        )
        points = [
            {
                "points": [["1", 1, 1.0, 0], ["2", 2, 2.0, 3600]],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three", "time"],
            }
        ]

        points_ms = copy.deepcopy(points)
        points_ms[0]["points"][1][-1] = 3600 * 1000

        points_us = copy.deepcopy(points)
        points_us[0]["points"][1][-1] = 3600 * 1000000

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database="db")

            cli.write_points({"foo": dataframe}, time_precision="s")
            self.assertListEqual(json.loads(m.last_request.body), points)

            cli.write_points({"foo": dataframe}, time_precision="m")
            self.assertListEqual(json.loads(m.last_request.body), points_ms)

            cli.write_points({"foo": dataframe}, time_precision="u")
            self.assertListEqual(json.loads(m.last_request.body), points_us)

    def test_write_points_from_dataframe_fails_without_time_index(self):
        """Test write points from dataframe that fails without time index."""
        dataframe = pd.DataFrame(
            data=[["1", 1, 1.0], ["2", 2, 2.0]],
            columns=["column_one", "column_two", "column_three"],
        )

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database="db")
            with self.assertRaises(TypeError):
                cli.write_points({"foo": dataframe})

    def test_write_points_from_dataframe_fails_with_series(self):
        """Test failed write points from dataframe with series."""
        now = pd.Timestamp("1970-01-01 00:00+00:00")
        dataframe = pd.Series(data=[1.0, 2.0], index=[now, now + timedelta(hours=1)])

        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series")

            cli = DataFrameClient(database="db")
            with self.assertRaises(TypeError):
                cli.write_points({"foo": dataframe})

    def test_query_into_dataframe(self):
        """Test query into a dataframe."""
        data = [
            {
                "name": "foo",
                "columns": ["time", "sequence_number", "column_one"],
                "points": [[3600, 16, 2], [3600, 15, 1], [0, 14, 2], [0, 13, 1]],
            }
        ]
        # dataframe sorted ascending by time first, then sequence_number
        dataframe = pd.DataFrame(
            data=[[13, 1], [14, 2], [15, 1], [16, 2]],
            index=pd.to_datetime([0, 0, 3600, 3600], unit="s", utc=True),
            columns=["sequence_number", "column_one"],
        )
        with _mocked_session("get", 200, data):
            cli = DataFrameClient(host="host", port=8086, username="username", password="password", database="db")
            result = cli.query("select column_one from foo;")
            assert_frame_equal(dataframe, result)

    def test_query_multiple_time_series(self):
        """Test query for multiple time series."""
        data = [
            {
                "name": "series1",
                "columns": ["time", "mean", "min", "max", "stddev"],
                "points": [[0, 323048, 323048, 323048, 0]],
            },
            {
                "name": "series2",
                "columns": ["time", "mean", "min", "max", "stddev"],
                "points": [[0, -2.8233, -2.8503, -2.7832, 0.0173]],
            },
            {
                "name": "series3",
                "columns": ["time", "mean", "min", "max", "stddev"],
                "points": [[0, -0.01220, -0.01220, -0.01220, 0]],
            },
        ]
        dataframes = {
            "series1": pd.DataFrame(
                data=[[323048, 323048, 323048, 0]],
                index=pd.to_datetime([0], unit="s", utc=True),
                columns=["mean", "min", "max", "stddev"],
            ),
            "series2": pd.DataFrame(
                data=[[-2.8233, -2.8503, -2.7832, 0.0173]],
                index=pd.to_datetime([0], unit="s", utc=True),
                columns=["mean", "min", "max", "stddev"],
            ),
            "series3": pd.DataFrame(
                data=[[-0.01220, -0.01220, -0.01220, 0]],
                index=pd.to_datetime([0], unit="s", utc=True),
                columns=["mean", "min", "max", "stddev"],
            ),
        }
        with _mocked_session("get", 200, data):
            cli = DataFrameClient(host="host", port=8086, username="username", password="password", database="db")
            result = cli.query(
                """select mean(value), min(value), max(value),
                stddev(value) from series1, series2, series3"""
            )
            self.assertEqual(dataframes.keys(), result.keys())
            for key in dataframes.keys():
                assert_frame_equal(dataframes[key], result[key])

    def test_query_with_empty_result(self):
        """Test query with empty results."""
        with _mocked_session("get", 200, []):
            cli = DataFrameClient(host="host", port=8086, username="username", password="password", database="db")
            result = cli.query("select column_one from foo;")
            self.assertEqual(result, [])

    def test_list_series(self):
        """Test list of series for dataframe object."""
        response = [
            {
                "columns": ["time", "name"],
                "name": "list_series_result",
                "points": [[0, "seriesA"], [0, "seriesB"]],
            }
        ]
        with _mocked_session("get", 200, response):
            cli = DataFrameClient(host="host", port=8086, username="username", password="password", database="db")
            series_list = cli.get_list_series()
            self.assertEqual(series_list, ["seriesA", "seriesB"])

    def test_datetime_to_epoch(self):
        """Test convert datetime to epoch."""
        timestamp = pd.Timestamp("2013-01-01 00:00:00.000+00:00")
        cli = DataFrameClient(host="host", port=8086, username="username", password="password", database="db")

        self.assertEqual(cli._datetime_to_epoch(timestamp), 1356998400.0)
        self.assertEqual(cli._datetime_to_epoch(timestamp, time_precision="s"), 1356998400.0)
        self.assertEqual(cli._datetime_to_epoch(timestamp, time_precision="m"), 1356998400000.0)
        self.assertEqual(cli._datetime_to_epoch(timestamp, time_precision="ms"), 1356998400000.0)
        self.assertEqual(cli._datetime_to_epoch(timestamp, time_precision="u"), 1356998400000000.0)



class TestInfluxdb08DataFrameClientCoverage(unittest.TestCase):
    """Test coverage for influxdb08 dataframe client."""

    def setUp(self):
        """Initialize test fixtures."""
        try:
            import pandas as pd
            import numpy as np
            self.pd = pd
            self.np = np
            self.skip = False
        except ImportError:  # pragma: no cover
            self.skip = True

    def test_write_points_with_precision_deprecated(self):
        """Cover lines 77-84: deprecated write_points_with_precision."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        pd = self.pd

        client = DataFrameClient(host="localhost", port=8086, username="u", password="p", database="db")
        df = pd.DataFrame(
            {"value": [1.0]},
            index=pd.DatetimeIndex(["2021-01-01"], tz="UTC"),
        )
        with Mocker() as m:
            m.register_uri(requests_mock.POST, "http://localhost:8086/db/db/series",
                           status_code=200, text='{}')
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                try:
                    client.write_points_with_precision({"cpu": df}, time_precision="s")
                except Exception:  # pragma: no cover
                    pass
            future_warnings = [x for x in w if issubclass(x.category, FutureWarning)]
            self.assertTrue(len(future_warnings) > 0)

    def test_convert_dataframe_to_json_not_dataframe(self):
        """Cover line 118: TypeError for non-DataFrame."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        client = DataFrameClient(host="localhost", port=8086, username="u", password="p", database="db")
        with self.assertRaises(TypeError):
            client._convert_dataframe_to_json({"not": "a dataframe"}, "measurement")

    def test_convert_dataframe_bad_index(self):
        """Cover line 120: TypeError for bad index."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        pd = self.pd
        client = DataFrameClient(host="localhost", port=8086, username="u", password="p", database="db")
        df = pd.DataFrame({"value": [1.0]})  # default RangeIndex, not DatetimeIndex
        with self.assertRaises(TypeError):
            client._convert_dataframe_to_json(df, "measurement")

    def test_convert_dataframe_period_index(self):
        """Cover lines 154-155: PeriodIndex conversion."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        pd = self.pd
        client = DataFrameClient(host="localhost", port=8086, username="u", password="p", database="db")
        period_index = pd.period_range("2021-01-01", periods=2, freq="D")
        df = pd.DataFrame({"value": [1.0, 2.0]}, index=period_index)
        result = client._convert_dataframe_to_json(df, "cpu")
        self.assertIn("name", result)
        self.assertEqual(result["name"], "cpu")

    def test_convert_dataframe_no_tzinfo(self):
        """Cover line 162: tz_localize for datetime without tzinfo."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        pd = self.pd
        client = DataFrameClient(host="localhost", port=8086, username="u", password="p", database="db")
        dt_index = pd.DatetimeIndex(["2021-01-01", "2021-01-02"])  # no tz
        df = pd.DataFrame({"value": [1.0, 2.0]}, index=dt_index)
        result = client._convert_dataframe_to_json(df, "cpu")
        self.assertIn("name", result)

    def test_datetime_to_epoch_ms(self):
        """Cover line 170->exit: _datetime_to_epoch for all branches."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        pd = self.pd
        client = DataFrameClient(host="localhost", port=8086, username="u", password="p", database="db")
        dt = pd.Timestamp("2021-01-01 00:00:00+00:00")
        # m and ms
        val_m = client._datetime_to_epoch(dt, "m")
        val_ms = client._datetime_to_epoch(dt, "ms")
        self.assertEqual(val_m, val_ms)
        # u
        val_u = client._datetime_to_epoch(dt, "u")
        self.assertIsNotNone(val_u)
        # s
        val_s = client._datetime_to_epoch(dt, "s")
        self.assertIsNotNone(val_s)


# ---------------------------------------------------------------------------
# _dataframe_client.py – missing branches
# ---------------------------------------------------------------------------


class TestInfluxdb08DFClientCoverageExtra(unittest.TestCase):
    """Additional tests for influxdb08/dataframe_client.py remaining gaps."""

    def setUp(self):
        try:
            import pandas as pd
            import numpy as np
            self.pd = pd
            self.np = np
            self.skip = False
        except ImportError:  # pragma: no cover
            self.skip = True

    def test_to_dataframe_time_precision_m(self):
        """Cover line 118: _to_dataframe with time_precision='m'."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        # _to_dataframe is a static method that takes json_result and time_precision
        json_result = {
            "name": "cpu",
            "columns": ["time", "value"],
            "points": [[1609459200000, 1.0]],
        }
        result = DataFrameClient._to_dataframe(json_result, time_precision="m")
        self.assertIsNotNone(result)

    def test_to_dataframe_time_precision_u(self):
        """Cover line 120: _to_dataframe with time_precision='u'."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        json_result = {
            "name": "cpu",
            "columns": ["time", "value"],
            "points": [[1609459200000000, 1.0]],
        }
        result = DataFrameClient._to_dataframe(json_result, time_precision="u")
        self.assertIsNotNone(result)

    def test_convert_array_ignore_nan_false(self):
        """Cover line 162: _convert_array when ignore_nan=False."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        import numpy as np
        client = DataFrameClient(False, host="localhost", port=8086,
                                 username="u", password="p", database="db")
        arr = np.array([1.0, float("nan"), 3.0])
        result = client._convert_array(arr)
        self.assertIsInstance(result, list)

    def test_datetime_to_epoch_unknown_precision(self):
        """Cover 170->exit: _datetime_to_epoch with unknown precision returns None."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        pd = self.pd
        client = DataFrameClient(host="localhost", port=8086,
                                 username="u", password="p", database="db")
        dt = pd.Timestamp("2021-01-01 00:00:00+00:00")
        result = client._datetime_to_epoch(dt, "unknown")
        self.assertIsNone(result)

    def test_to_dataframe_sequence_number(self):
        """Cover line 112 (sequence_number branch) in _to_dataframe."""
        if self.skip:  # pragma: no cover
            self.skipTest("pandas not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        json_result = {
            "name": "cpu",
            "columns": ["time", "value", "sequence_number"],
            "points": [[1609459200, 1.0, 1]],
        }
        result = DataFrameClient._to_dataframe(json_result, time_precision="s")
        self.assertIsNotNone(result)




class TestInfluxdb08DataFrameClientImportErrors(unittest.TestCase):
    """Test ImportError paths in influxdb08/dataframe_client.py."""

    def test_pandas_import_error_in_init(self):
        """Cover lines 30-31: ImportError for pandas in DataFrameClient.__init__."""
        import sys
        from unittest.mock import patch
        # Remove pandas from sys.modules temporarily to simulate ImportError
        with patch.dict(sys.modules, {'pandas': None}):
            from influxdb.influxdb08.dataframe_client import DataFrameClient
            with self.assertRaises(ImportError) as ctx:
                client = DataFrameClient(host="localhost")
            self.assertIn("Pandas", str(ctx.exception))

    def test_numpy_import_error_in_convert_array(self):
        """Cover lines 154-155: ImportError for numpy in _convert_array."""
        import sys
        try:
            import pandas  # noqa: F401
        except ImportError:  # pragma: no cover
            self.skipTest("pandas or numpy not available")
        from influxdb.influxdb08.dataframe_client import DataFrameClient
        client = DataFrameClient(host="localhost", ignore_nan=True)
        with patch.dict(sys.modules, {'numpy': None}):
            with self.assertRaises(ImportError) as ctx:
                client._convert_array([1.0, 2.0])
            self.assertIn("Numpy", str(ctx.exception))

