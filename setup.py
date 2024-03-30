import setuptools

with open("README_old.md", "r", encoding="utf-8") as fh:
    coverage_string: str = "![Coverage report](https://github.com/ZPascal/influxdb_api_sdk/blob/main/docs/coverage.svg)"
    long_description: str = fh.read()

long_description = long_description.replace(coverage_string, "")

setuptools.setup(
    name="influxdb-api-sdk",
    version="6.0.1",
    author="Pascal Zimmermann",
    author_email="info@theiotstudio.com",
    description="A InfluxDB API SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ZPascal/influxdb_api_sdk",
    project_urls={
        "Source": "https://github.com/ZPascal/influxdb_api_sdk",
        "Bug Tracker": "https://github.com/ZPascal/influxdb_api_sdk/issues",
        "Documentation": "https://zpascal.github.io/influxdb_api_sdk/",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved",
        "Operating System :: OS Independent",
    ],
    license="Apache-2.0 License",
    packages=["influxdb"],
    install_requires=["python-dateutil", "pytz", "urllib3", "msgpack"],
    tests_require=["pytest", "pandas", "numpy"],
    python_requires=">=3.8",
)
