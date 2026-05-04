# -*- coding: utf-8 -*-
"""Define the resultset test package."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import warnings

from influxdb.exceptions import InfluxDBClientError
from influxdb.resultset import ResultSet


class TestResultSet(unittest.TestCase):
    """Define the ResultSet test object."""

    def setUp(self):
        """Set up an instance of TestResultSet."""
        self.query_response = {
            "results": [
                {
                    "series": [
                        {
                            "name": "cpu_load_short",
                            "columns": ["time", "value", "host", "region"],
                            "values": [
                                [
                                    "2015-01-29T21:51:28.968422294Z",
                                    0.64,
                                    "server01",
                                    "us-west",
                                ],
                                [
                                    "2015-01-29T21:51:28.968422294Z",
                                    0.65,
                                    "server02",
                                    "us-west",
                                ],
                            ],
                        },
                        {
                            "name": "other_series",
                            "columns": ["time", "value", "host", "region"],
                            "values": [
                                [
                                    "2015-01-29T21:51:28.968422294Z",
                                    0.66,
                                    "server01",
                                    "us-west",
                                ],
                            ],
                        },
                    ]
                }
            ]
        }

        self.rs = ResultSet(self.query_response["results"][0])

    def test_filter_by_name(self):
        """Test filtering by name in TestResultSet object."""
        expected = [
            {
                "value": 0.64,
                "time": "2015-01-29T21:51:28.968422294Z",
                "host": "server01",
                "region": "us-west",
            },
            {
                "value": 0.65,
                "time": "2015-01-29T21:51:28.968422294Z",
                "host": "server02",
                "region": "us-west",
            },
        ]

        self.assertEqual(expected, list(self.rs.get_points(measurement="cpu_load_short")))

    def test_filter_by_tags(self):
        """Test filter by tags in TestResultSet object."""
        expected = [
            {
                "value": 0.64,
                "time": "2015-01-29T21:51:28.968422294Z",
                "host": "server01",
                "region": "us-west",
            },
            {
                "value": 0.66,
                "time": "2015-01-29T21:51:28.968422294Z",
                "host": "server01",
                "region": "us-west",
            },
        ]

        self.assertEqual(expected, list(self.rs.get_points(tags={"host": "server01"})))

    def test_filter_by_name_and_tags(self):
        """Test filter by name and tags in TestResultSet object."""
        self.assertEqual(
            list(self.rs.get_points(measurement="cpu_load_short", tags={"host": "server01"})),
            [
                {
                    "value": 0.64,
                    "time": "2015-01-29T21:51:28.968422294Z",
                    "host": "server01",
                    "region": "us-west",
                }
            ],
        )

        self.assertEqual(
            list(self.rs.get_points(measurement="cpu_load_short", tags={"region": "us-west"})),
            [
                {
                    "value": 0.64,
                    "time": "2015-01-29T21:51:28.968422294Z",
                    "host": "server01",
                    "region": "us-west",
                },
                {
                    "value": 0.65,
                    "time": "2015-01-29T21:51:28.968422294Z",
                    "host": "server02",
                    "region": "us-west",
                },
            ],
        )

    def test_keys(self):
        """Test keys in TestResultSet object."""
        self.assertEqual(
            self.rs.keys(),
            [
                ("cpu_load_short", None),
                ("other_series", None),
            ],
        )

    def test_len(self):
        """Test length in TestResultSet object."""
        self.assertEqual(len(self.rs), 2)

    def test_items(self):
        """Test items in TestResultSet object."""
        items = list(self.rs.items())
        items_lists = [(item[0], list(item[1])) for item in items]

        self.assertEqual(
            items_lists,
            [
                (
                    ("cpu_load_short", None),
                    [
                        {
                            "time": "2015-01-29T21:51:28.968422294Z",
                            "value": 0.64,
                            "host": "server01",
                            "region": "us-west",
                        },
                        {
                            "time": "2015-01-29T21:51:28.968422294Z",
                            "value": 0.65,
                            "host": "server02",
                            "region": "us-west",
                        },
                    ],
                ),
                (
                    ("other_series", None),
                    [
                        {
                            "time": "2015-01-29T21:51:28.968422294Z",
                            "value": 0.66,
                            "host": "server01",
                            "region": "us-west",
                        }
                    ],
                ),
            ],
        )

    def test_point_from_cols_vals(self):
        """Test points from columns in TestResultSet object."""
        cols = ["col1", "col2"]
        vals = [1, "2"]

        point = ResultSet.point_from_cols_vals(cols, vals)
        self.assertDictEqual(point, {"col1": 1, "col2": "2"})

    def test_system_query(self):
        """Test system query capabilities in TestResultSet object."""
        rs = ResultSet(
            {
                "series": [
                    {
                        "values": [
                            ["another", "48h0m0s", 3, False],
                            ["default", "0", 1, False],
                            ["somename", "24h0m0s", 4, True],
                        ],
                        "columns": ["name", "duration", "replicaN", "default"],
                    }
                ]
            }
        )

        self.assertEqual(rs.keys(), [("results", None)])

        self.assertEqual(
            list(rs.get_points(measurement="results")),
            [
                {
                    "duration": "48h0m0s",
                    "default": False,
                    "replicaN": 3,
                    "name": "another",
                },
                {"duration": "0", "default": False, "replicaN": 1, "name": "default"},
                {
                    "duration": "24h0m0s",
                    "default": True,
                    "replicaN": 4,
                    "name": "somename",
                },
            ],
        )

    def test_resultset_error(self):
        """Test returning error in TestResultSet object."""
        with self.assertRaises(InfluxDBClientError):
            ResultSet({"series": [], "error": "Big error, many problems."})



class TestResultSetCoverage(unittest.TestCase):
    def test_raw_setter(self):
        """Cover the raw.setter (line 40)."""
        rs = ResultSet({"series": []})
        rs.raw = {"series": [{"name": "new", "columns": ["time"], "values": []}]}
        self.assertIn("series", rs.raw)

    def test_getitem_tuple_wrong_len(self):
        """Cover the TypeError for tuple with wrong length (line 74)."""
        rs = ResultSet({"series": []})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with self.assertRaises(TypeError):
                list(rs[(1, 2, 3)])

    def test_getitem_tuple_tags_not_dict(self):
        """Cover the TypeError for non-dict tags (line 80)."""
        rs = ResultSet({"series": []})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with self.assertRaises(TypeError):
                list(rs[("name", "not_a_dict")])

    def test_get_points_measurement_type_error(self):
        """Cover TypeError when measurement is not str/None (line 106)."""
        rs = ResultSet({"series": []})
        with self.assertRaises(TypeError):
            list(rs.get_points(measurement=123))

    def test_series_name_none_with_tags_skipped(self):
        """Cover branch: series_name is None and tags is not None (lines 114-116)."""
        rs = ResultSet(
            {
                "series": [
                    {
                        "columns": ["name", "duration"],
                        "values": [["rp1", "0"]],
                    }
                ]
            }
        )
        # series_name will be "results" (no name/measurement key), not None,
        # so create a patched series that returns None for name lookup
        rs._raw = {
            "series": [
                {
                    "name": None,
                    "columns": ["col"],
                    "values": [["v"]],
                }
            ]
        }
        # tags is not None → should be skipped
        result = list(rs.get_points(measurement=None, tags={"host": "server01"}))
        self.assertEqual(result, [])

    def test_series_name_none_without_tags_yields(self):
        """Cover branch: series_name is None and tags is None → yields points."""
        rs = ResultSet({"series": []})
        rs._raw = {
            "series": [
                {
                    "name": None,
                    "columns": ["col"],
                    "values": [["v"]],
                }
            ]
        }
        result = list(rs.get_points(measurement=None, tags=None))
        self.assertEqual(result, [{"col": "v"}])

    def test_iter(self):
        """Cover __iter__ (lines 137-138)."""
        rs = ResultSet(
            {
                "series": [
                    {
                        "name": "cpu",
                        "columns": ["time", "value"],
                        "values": [["2021-01-01", 1.0]],
                    }
                ]
            }
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            items = list(rs)
        self.assertEqual(len(items), 1)


class TestResultSetGetitemCoverage(unittest.TestCase):
    """Cover alternative __getitem__ branches that aren't used in normal flow."""

    def setUp(self):
        """Initialize result set with test data."""
        self.rs = ResultSet(
            {
                "series": [
                    {
                        "name": "cpu_load_short",
                        "columns": ["time", "value", "host", "region"],
                        "values": [
                            ["2015-01-29T21:51:28.968422294Z", 0.64, "server01", "us-west"],
                            ["2015-01-29T21:51:28.968422294Z", 0.66, "server01", "us-west"],
                            ["2015-01-29T21:51:28.968422294Z", 0.65, "server02", "us-west"],
                        ],
                    }
                ]
            }
        )

    def test_getitem_with_dict_key(self):
        """Cover __getitem__ with dict key (tags filter only)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = list(self.rs[{"host": "server01"}])
        # Dict key uses get_points(measurement=None, tags=...), which filters by tags
        self.assertEqual(len(result), 2)

    def test_getitem_with_string_key(self):
        """Cover __getitem__ with string key (measurement filter only)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = list(self.rs["cpu_load_short"])
        # String key uses get_points(measurement=key, tags=None)
        self.assertEqual(len(result), 3)

    def test_getitem_with_tuple_key(self):
        """Cover __getitem__ with tuple key (measurement + tags filter)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = list(self.rs[("cpu_load_short", {"host": "server01"})])
        # Tuple key uses get_points(measurement=name, tags=tags)
        self.assertEqual(len(result), 2)

    def test_getitem_invalid_tags_type(self):
        """Cover TypeError when tags is not dict or None."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with self.assertRaises(TypeError):
                list(self.rs[("cpu_load_short", "invalid_tags_type")])


class TestResultSetRepr(unittest.TestCase):
    """Test __repr__ of ResultSet."""

    def test_repr(self):
        """Test __repr__ method."""
        rs = ResultSet(
            {
                "series": [
                    {
                        "name": "cpu",
                        "columns": ["time", "value"],
                        "values": [["2021-01-01", 1.0]],
                    }
                ]
            }
        )
        repr_str = repr(rs)
        self.assertIn("ResultSet", repr_str)
        self.assertIn("'cpu'", repr_str)


# ---------------------------------------------------------------------------
# line_protocol.py – missing branches
# ---------------------------------------------------------------------------

