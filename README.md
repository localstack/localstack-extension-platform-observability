LocalStack Extension: Platform observability
===============================

LocalStack extension for providing insights into the LocalStack platform in the form of service-specific traces and metrics.

## Install

```bash
localstack extensions install localstack-extension-platform-observability
```

## Install local development version

To install the extension into localstack in developer mode, you will need Python 3.10, and create a virtual environment in the extensions project.

In the newly generated project, simply run

```bash
make install
```

Then, to enable the extension for LocalStack, run

```bash
localstack extensions dev enable .
```

You can then start LocalStack with `EXTENSION_DEV_MODE=1` to load all enabled extensions:

```bash
EXTENSION_DEV_MODE=1 localstack start
```

## Install from GitHub repository

To distribute your extension, simply upload it to your github account. Your extension can then be installed via:

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extension-platform-observability/#egg=localstack-extension-platform-observability"
```

## Usage


Fetch aggregated metrics and system metrics

```bash
curl localhost:4566/_extension/metrics/all
```

Fetch SNS statistics

```bash
curl localhost:4566/_extension/metrics/sns
```

Fetch SQS statistics

```bash
curl localhost:4566/_extension/metrics/sqs
```

Find lambda traces in
```bash
/var/lib/localstack/cache/metrics/lambda-traces/
```
