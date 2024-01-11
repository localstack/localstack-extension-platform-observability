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

### Metrics

Fetch all metrics

```bash
curl localhost:4566/_extension/observability/metrics
```

Fetch a specific instrument

```bash
curl localhost:4566/_extension/observability/metrics/<instrument>
```

The following instruments exist
* `system`: system metrics like number of threads
* `sns`: sns topic statistics
* `sqs`: sqs queue statistics
* `gateway`: HTTP gateway statistics on number of requests

Example:

```bash
curl -s "localhost:4566/_extension/observability/metrics" | jq .
```
```json
{
  "system": [
    {
      "active_thread_count": 15,
      "max_rss": 15
    }
  ],
  "gateway": [
    {
      "total": 14,
      "sqs.SendMessage": 2,
      "sqs.ReceiveMessage": 1,
      "sns.Publish": 1,
      "dynamodb.PutItem": 0,
      "dynamodb.GetItem": 0,
      "dynamodb.BatchWriteItem": 0,
      "dynamodb.BatchGetItem": 0,
      "lambda.Invoke": 0
    }
  ],
  "sqs": [
    {
      "queue": "arn:aws:sqs:us-east-1:000000000000:input-dead-letter-queue",
      "visible": 0,
      "invisible": 0,
      "delayed": 0
    },
    {
      "queue": "arn:aws:sqs:us-east-1:000000000000:input-queue",
      "visible": 2,
      "invisible": 0,
      "delayed": 0
    },
    {
      "queue": "arn:aws:sqs:us-east-1:000000000000:recovery-queue",
      "visible": 0,
      "invisible": 0,
      "delayed": 0
    }
  ],
  "sns": [
    {
      "topic_arn": "arn:aws:sns:us-east-1:000000000000:localstack-topic",
      "published": 1,
      "delivered": 0,
      "failed": 0
    }
  ],
  "timestamp": 1704986115.3762584
}
```


### Trace logs

#### Lambda

Find lambda traces in
```bash
/var/lib/localstack/cache/observability/traces-lambda-events/
```

Here is an example:

```json
{"timestamp": 1704984270.1660516, "event": "enqueued", "request_id": "ad2df0ed-c952-4f48-881c-8b944dad44c6", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-e0c504b2", "failure_cause": null}
{"timestamp": 1704984270.184178, "event": "enqueued", "request_id": "d5d2efb3-e781-411a-b718-e2345c118c39", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-e0c504b2", "failure_cause": null}
{"timestamp": 1704984270.3365452, "event": "submitted", "request_id": "ad2df0ed-c952-4f48-881c-8b944dad44c6", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-e0c504b2", "failure_cause": null}
{"timestamp": 1704984270.3368104, "event": "invoking", "request_id": "ad2df0ed-c952-4f48-881c-8b944dad44c6", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-e0c504b2", "failure_cause": null}
{"timestamp": 1704984270.4253993, "event": "submitted", "request_id": "d5d2efb3-e781-411a-b718-e2345c118c39", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-e0c504b2", "failure_cause": null}
```


#### Lambda SQS Event source listeners

Find traces that relate to lambda sqs event source listeners in
```bash
/var/lib/localstack/cache/observability/traces-lambda-sqs/
```

Here is an example of queueing two message to trigger a lambda.

```json
{"timestamp": 1705009138.683765, "event": "message_queued", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": null, "request_id": null, "failure_cause": null}
{"timestamp": 1705009138.6840491, "event": "message_queued", "message_id": "00787a9f-1d70-452d-9fec-f25bf7064e32", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": null, "request_id": null, "failure_cause": null}
{"timestamp": 1705009139.6799114, "event": "message_dequeued", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": null, "failure_cause": null}
{"timestamp": 1705009139.6799738, "event": "invoke_queued", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "0d616a5e-2511-4c88-a7b2-de0f0a7161ed", "failure_cause": null}
{"timestamp": 1705009139.6801724, "event": "invoke", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "0d616a5e-2511-4c88-a7b2-de0f0a7161ed", "failure_cause": null}
{"timestamp": 1705009140.0882578, "event": "invoke_success", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "0d616a5e-2511-4c88-a7b2-de0f0a7161ed", "failure_cause": null}
{"timestamp": 1705009140.6862357, "event": "message_dequeued", "message_id": "00787a9f-1d70-452d-9fec-f25bf7064e32", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": null, "failure_cause": null}
{"timestamp": 1705009140.6865497, "event": "invoke_queued", "message_id": "00787a9f-1d70-452d-9fec-f25bf7064e32", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "101a0017-172b-401b-9381-34aa1a4d3e7c", "failure_cause": null}
{"timestamp": 1705009140.6868262, "event": "invoke", "message_id": "00787a9f-1d70-452d-9fec-f25bf7064e32", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "101a0017-172b-401b-9381-34aa1a4d3e7c", "failure_cause": null}
{"timestamp": 1705009140.6951976, "event": "invoke_success", "message_id": "00787a9f-1d70-452d-9fec-f25bf7064e32", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "101a0017-172b-401b-9381-34aa1a4d3e7c", "failure_cause": null}
```