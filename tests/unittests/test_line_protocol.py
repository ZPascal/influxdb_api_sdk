# -*- coding: utf-8 -*-
"""Define the line protocol test module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from datetime import datetime
from decimal import Decimal

from pytz import UTC, timezone
from influxdb import line_protocol
from influxdb.line_protocol import _escape_tag_value, _convert_timestamp, _is_float, _escape_value, _get_unicode, \
    make_line


class TestLineProtocol(unittest.TestCase):
    """Define the LineProtocol test object."""

    def test_make_lines(self):
        """Test make new lines in TestLineProtocol object."""
        data = {
            "tags": {
                "empty_tag": "",
                "none_tag": None,
                "backslash_tag": "C:\\",
                "integer_tag": 2,
                "string_tag": "hello",
            },
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "string_val": "hello!",
                        "int_val": 1,
                        "float_val": 1.1,
                        "none_field": None,
                        "bool_val": True,
                    },
                }
            ],
        }

        self.assertEqual(
            line_protocol.make_lines(data),
            "test,backslash_tag=C:\\\\,integer_tag=2,string_tag=hello "
            'bool_val=True,float_val=1.1,int_val=1i,string_val="hello!"\n',
        )

    def test_timezone(self):
        """Test timezone in TestLineProtocol object."""
        dt = datetime(2009, 11, 10, 23, 0, 0, 123456)
        utc = UTC.localize(dt)
        berlin = timezone("Europe/Berlin").localize(dt)
        eastern = berlin.astimezone(timezone("US/Eastern"))
        data = {
            "points": [
                {"measurement": "A", "fields": {"val": 1}, "time": 0},
                {
                    "measurement": "A",
                    "fields": {"val": 1},
                    "time": "2009-11-10T23:00:00.123456Z",
                },
                {"measurement": "A", "fields": {"val": 1}, "time": dt},
                {"measurement": "A", "fields": {"val": 1}, "time": utc},
                {"measurement": "A", "fields": {"val": 1}, "time": berlin},
                {"measurement": "A", "fields": {"val": 1}, "time": eastern},
            ]
        }
        self.assertEqual(
            line_protocol.make_lines(data),
            "\n".join(
                [
                    "A val=1i 0",
                    "A val=1i 1257894000123456000",
                    "A val=1i 1257894000123456000",
                    "A val=1i 1257894000123456000",
                    "A val=1i 1257890400123456000",
                    "A val=1i 1257890400123456000",
                ]
            )
            + "\n",
        )

    def test_string_val_newline(self):
        """Test string value with newline in TestLineProtocol object."""
        data = {"points": [{"measurement": "m1", "fields": {"multi_line": "line1\nline1\nline3"}}]}

        self.assertEqual(line_protocol.make_lines(data), 'm1 multi_line="line1\\nline1\\nline3"\n')

    def test_make_lines_unicode(self):
        """Test make unicode lines in TestLineProtocol object."""
        data = {
            "tags": {"unicode_tag": "'Привет!'"},  # Hello! in Russian
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "unicode_val": "Привет!",  # Hello! in Russian
                    },
                }
            ],
        }

        self.assertEqual(
            line_protocol.make_lines(data),
            "test,unicode_tag='Привет!' unicode_val=\"Привет!\"\n",
        )

    def test_make_lines_empty_field_string(self):
        """Test make lines with an empty string field."""
        data = {
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "string": "",
                    },
                }
            ]
        }

        self.assertEqual(line_protocol.make_lines(data), 'test string=""\n')

    def test_tag_value_newline(self):
        """Test make lines with tag value contains newline."""
        data = {
            "tags": {"t1": "line1\nline2"},
            "points": [{"measurement": "test", "fields": {"val": "hello"}}],
        }

        self.assertEqual(line_protocol.make_lines(data), 'test,t1=line1\\nline2 val="hello"\n')

    def test_quote_ident(self):
        """Test quote indentation in TestLineProtocol object."""
        self.assertEqual(
            line_protocol.quote_ident(r"""\foo ' bar " Örf"""),
            r'''"\\foo ' bar \" Örf"''',
        )

    def test_quote_literal(self):
        """Test quote literal in TestLineProtocol object."""
        self.assertEqual(
            line_protocol.quote_literal(r"""\foo ' bar " Örf"""),
            r"""'\\foo \' bar " Örf'""",
        )

    def test_float_with_long_decimal_fraction(self):
        """Ensure precision is preserved when casting floats into strings."""
        data = {
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "float_val": 1.0000000000000009,
                    },
                }
            ]
        }
        self.assertEqual(line_protocol.make_lines(data), "test float_val=1.0000000000000009\n")

    def test_float_with_long_decimal_fraction_as_type_decimal(self):
        """Ensure precision is preserved when casting Decimal into strings."""
        data = {
            "points": [
                {
                    "measurement": "test",
                    "fields": {
                        "float_val": Decimal(0.8289445733333332),
                    },
                }
            ]
        }
        self.assertEqual(line_protocol.make_lines(data), "test float_val=0.8289445733333332\n")



class TestLineProtocolCoverage(unittest.TestCase):
    """Test coverage for line protocol edge cases."""

    def test_convert_timestamp_raises_value_error(self):
        """Test that invalid timestamp raises ValueError."""
        with self.assertRaises(ValueError):
            _convert_timestamp("not a valid timestamp at all %%%")

    def test_escape_tag_value_trailing_backslash(self):
        """Test escaping tag value with trailing backslash."""
        result = _escape_tag_value("C:\\")
        self.assertTrue(result.endswith(" "))

    def test_is_float_type_error(self):
        """Test is_float with None type."""
        self.assertFalse(_is_float(None))

    def test_is_float_value_error(self):
        """Test is_float with non-float string."""
        self.assertFalse(_is_float("not_a_float"))

    def test_escape_value_float(self):
        """Test escaping Decimal value."""
        from decimal import Decimal
        result = _escape_value(Decimal("3.14"))
        self.assertIn("3.14", result)

    def test_get_unicode_none(self):
        """Test get_unicode with None."""
        self.assertEqual(_get_unicode(None), "")

    def test_get_unicode_force(self):
        """Test get_unicode with force option."""
        self.assertEqual(_get_unicode(42, force=True), "42")

    def test_make_line_no_fields_no_time(self):
        """Test make_line with no fields or time."""
        result = make_line("measurement", tags={}, fields={})
        self.assertEqual(result, "measurement")

    def test_convert_timestamp_precision_u(self):
        """Cover precision 'u' in _convert_timestamp."""
        from datetime import datetime
        from pytz import UTC
        dt = UTC.localize(datetime(2020, 1, 1))
        result = _convert_timestamp(dt, precision="u")
        self.assertIsNotNone(result)

    def test_convert_timestamp_precision_ms(self):
        """Cover precision 'ms'."""
        from datetime import datetime
        from pytz import UTC
        dt = UTC.localize(datetime(2020, 1, 1))
        result = _convert_timestamp(dt, precision="ms")
        self.assertIsNotNone(result)

    def test_convert_timestamp_precision_m(self):
        """Cover precision 'm'."""
        from datetime import datetime
        from pytz import UTC
        dt = UTC.localize(datetime(2020, 1, 1))
        result = _convert_timestamp(dt, precision="m")
        self.assertIsNotNone(result)

    def test_convert_timestamp_precision_h(self):
        """Cover precision 'h'."""
        from datetime import datetime
        from pytz import UTC
        dt = UTC.localize(datetime(2020, 1, 1))
        result = _convert_timestamp(dt, precision="h")
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# client.py – missing branches
# ---------------------------------------------------------------------------


class TestLineProtocolCoverageExtra(unittest.TestCase):
    """Extra tests for line_protocol.py coverage gaps."""

    def test_convert_timestamp_not_convertible(self):
        """Cover line 56: raise ValueError when timestamp is not string/datetime/int."""
        with self.assertRaises(ValueError):
            _convert_timestamp([1, 2, 3])

    def test_escape_tag_value_no_trailing_backslash(self):
        """Cover 66->68 False branch: tag value without trailing backslash."""
        result = _escape_tag_value("hello world")
        self.assertIn("hello", result)

    def test_escape_value_non_float_object(self):
        """Cover line 123: str(value) for non-float-convertible object."""
        class NonFloat:
            def __str__(self):
                return "nonfloat"
            def __float__(self):
                raise TypeError("not a float")

        result = _escape_value(NonFloat())
        self.assertEqual(result, "nonfloat")

    def test_get_unicode_bytes(self):
        """Cover line 138: _get_unicode returns decoded str for bytes input."""
        result = _get_unicode(b"hello")
        self.assertEqual(result, "hello")

    def test_pandas_time_unit_s(self):
        """Cover 25->27 in _pandas_time_unit: time_precision='s' skips all elif."""
        from influxdb._dataframe_client import _pandas_time_unit
        self.assertEqual(_pandas_time_unit("s"), "s")




class TestLineProtocolInvalidPrecisionDatetime(unittest.TestCase):
    """Test line_protocol.py 53->56: datetime with invalid precision raises ValueError."""

    def test_convert_timestamp_datetime_invalid_precision(self):
        """Cover 53->56: datetime with unsupported precision raises ValueError."""
        from datetime import datetime
        from influxdb.line_protocol import _convert_timestamp
        dt = datetime(2021, 1, 1, 0, 0, 0)
        with self.assertRaises(ValueError):
            _convert_timestamp(dt, precision="invalid")

