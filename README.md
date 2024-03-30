# Grafana API SDK ![Coverage report](https://github.com/ZPascal/influxdb_api_sdk/blob/main/docs/coverage.svg)
The repository includes an SDK for the InfluxDB v1 API and the Flux compatibility layer above InfluxDB version 1.8. It's possible to interact with all publicly available InfluxDB HTTP API endpoints supported by the [influxdb-python](https://github.com/influxdata/influxdb-python) client.

## Differences between the [influxdb-python](https://github.com/influxdata/influxdb-python) and the [influxdb_api_sdk](https://github.com/ZPascal/influxdb_api_sdk)

#TODO Adjust the documentation

The grafana-client is only a fork of the non-maintained grafana_api repository. In general, the grafana-client project started at the same time, as I started this project. The corresponding SDK is a completely new project based on nonother projects and includes a few features that are currently not implemented inside the grafana-client.  

The core features that are implemented inside this library:

- All public Grafana API (HTTP) endpoints are supported
- Full API support for Grafana legacy alerting, current alerting, alerting channels, and alert provisioning
- Possibility to specify custom and self-signed certificates
- HTTP/2 support

In general, my focus on this project is to implement and deliver old and new features from the Grafana API, to document all features and functionality clear,ly and to increase the overall test coverage of the project.

## Installation

Please be aware to not install the `influxdb` and `influxdb-api-sdk` packages in parallel and the same environment. This result in name clashes, and it's not possible to use the InfluxDB API SDK.

`pip install influxdb-api-sdk`

## Example

```python
import json

from grafana_api.model import APIModel
from grafana_api.dashboard import Dashboard

model: APIModel = APIModel(host="test", token="test")

dashboard: Dashboard = Dashboard(model)

with open("/tmp/test/test.json") as file:
    json_dashboard = json.load(file)

dashboard.create_or_update_dashboard(message="Create a new test dashboard", dashboard_json=json_dashboard, dashboard_path="test")
```

## TLS/ mTLS

It is possible to pass a custom ssl_context to the underlying library to perform the requests to the HTTP API. For this step and to support custom TLS/ mTLS, there is an option to inject the Python ssl_context. More information can be found [here](https://docs.python.org/3/library/ssl.html#ssl.create_default_context) and a dummy TLS/ mTLS implementation below.

### TLS

```python
import ssl

from grafana_api.model import APIModel

ssl_ctx = ssl.create_default_context(
    ssl.Purpose.SERVER_AUTH,
    cafile="/test/path/ca.crt"
)
ssl_ctx.verify_mode = ssl.CERT_REQUIRED

model: APIModel = APIModel(host="test", token="test", ssl_context=ssl_ctx)
```

### mTLS

```python
import ssl

from grafana_api.model import APIModel

ssl_ctx = ssl.create_default_context(
    ssl.Purpose.SERVER_AUTH,
    cafile="/test/path/ca.crt",
)
ssl_ctx.verify_mode = ssl.CERT_REQUIRED
ssl_ctx.load_cert_chain(certfile="/test/path/client.crt", keyfile="/test/path/client.key",)

model: APIModel = APIModel(host="test", token="test", ssl_context=ssl_ctx)
```

## Contribution
If you would like to contribute something, have an improvement request, or want to make a change inside the code, please open a pull request.

## Support
If you need support, or you encounter a bug, please don't hesitate to open an issue.

## Donations
If you would like to support my work, I ask you to take an unusual action inside the open source community. Donate the money to a non-profit organization like Doctors Without Borders or the Children's Cancer Aid. I will continue to build tools because I like it, and it is my passion to develop and share applications.

## License
This product is available under the Apache 2.0 license.