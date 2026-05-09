# InfluxDB API SDK

The repository includes an SDK for the InfluxDB v1 API and the Flux compatibility layer above InfluxDB version 1.8. It is possible to interact with all publicly available InfluxDB HTTP API endpoints supported by the [influxdb-python](https://github.com/influxdata/influxdb-python) client.

## Differences between the [influxdb-python](https://github.com/influxdata/influxdb-python) and the [influxdb_api_sdk](https://github.com/ZPascal/influxdb_api_sdk)

The `influxdb_api_sdk` is a maintained fork of the unmaintained `influxdb-python` client. The core differences are:

- Uses `urllib3` instead of `requests` for HTTP communication
- Supports msgpack encoding for more efficient data transfer
- Supports custom TCP socket options
- Supports custom SSL contexts for TLS/mTLS
- Python 3.10+ only (no Python 2 support)
- Modern `pyproject.toml`-based packaging

The core features implemented in this library:

- All public InfluxDB v1 HTTP API endpoints are supported
- Flux query support (InfluxDB 1.8+)
- Possibility to specify custom and self-signed certificates via `ssl_context`
- UDP write support
- DataFrame client for pandas integration
- msgpack response encoding support

## Installation

Please be aware not to install the `influxdb` and `influxdb-api-sdk` packages in parallel in the same environment. This results in name clashes and it is not possible to use the InfluxDB API SDK.

```
pip install influxdb-api-sdk
```

For DataFrame support:

```
pip install influxdb-api-sdk[dataframe]
```

## Example

```python
from influxdb import InfluxDBClient

client = InfluxDBClient(host="localhost", port=8086, username="root", password="root", database="mydb")

# Write data
client.write_points([
    {
        "measurement": "cpu_load",
        "tags": {"host": "server01"},
        "time": "2024-01-01T00:00:00Z",
        "fields": {"value": 0.64}
    }
])

# Query data
result = client.query("SELECT * FROM cpu_load")
for point in result.get_points():
    print(point)

client.close()
```

## Context Manager

The client can be used as a context manager:

```python
from influxdb import InfluxDBClient

with InfluxDBClient(host="localhost", port=8086, database="mydb") as client:
    client.write_points([...])
```

## TLS / mTLS

It is possible to pass a custom `ssl_context` to the client to perform requests over HTTPS. More information can be found [here](https://docs.python.org/3/library/ssl.html#ssl.create_default_context).

### TLS

```python
import ssl
from influxdb import InfluxDBClient

ssl_ctx = ssl.create_default_context(
    ssl.Purpose.SERVER_AUTH,
    cafile="/path/to/ca.crt"
)
ssl_ctx.verify_mode = ssl.CERT_REQUIRED

client = InfluxDBClient(host="localhost", port=8086, ssl_usage=True, ssl_context=ssl_ctx)
```

### mTLS

```python
import ssl
from influxdb import InfluxDBClient

ssl_ctx = ssl.create_default_context(
    ssl.Purpose.SERVER_AUTH,
    cafile="/path/to/ca.crt",
)
ssl_ctx.verify_mode = ssl.CERT_REQUIRED
ssl_ctx.load_cert_chain(certfile="/path/to/client.crt", keyfile="/path/to/client.key")

client = InfluxDBClient(host="localhost", port=8086, ssl_usage=True, ssl_context=ssl_ctx)
```

## Custom Socket Options

Custom TCP socket options can be passed to control keep-alive and other low-level settings:

```python
import socket
from urllib3.connection import HTTPConnection
from influxdb import InfluxDBClient

socket_options = HTTPConnection.default_socket_options + [
    (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
    (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 60),
    (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 15),
]

client = InfluxDBClient(host="localhost", port=8086, socket_options=socket_options)
```

## Flux Queries (InfluxDB 1.8+)

```python
from influxdb import InfluxDBClient

client = InfluxDBClient(host="localhost", port=8086)

result = client.query(
    'from(bucket: "mydb/autogen") |> range(start: -1h)',
    headers={"Content-Type": "application/vnd.flux"}
)
```

## Contribution

If you would like to contribute something, have an improvement request, or want to make a change inside the code, please open a pull request.

## Support

If you need support, or you encounter a bug, please don't hesitate to open an issue.

## Donations

If you want to support my work, I ask you to take an unusual action inside the open source community. Donate the money to a non-profit organization like Doctors Without Borders or the Children's Cancer Aid. I will continue to build tools because I like them, and I am passionate about developing and sharing applications.

## License

This product is available under the Apache 2.0 license.
