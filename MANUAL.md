# Usage of the localstack metrics inspection extension

In this document we will shortly explore how to use this extension, how to get the data from it, and what tools we provide (as a way to start) to analyze the metrics we are capturing.

## Performance metric endpoint

As mentioned in the `README.md`, there are several endpoints you can use to query current metrics from your LocalStack instance.
There are multiple endpoints available, here we discuss the fields of the general endpoint, all others are subsets of it.

```json
{
  "system": [
    {
      "active_thread_count": 15,  # current number of threads running in the LocalStack main process
      "max_rss": 15  # resident set size
    }
  ],
  "gateway": [
    {
      "total": 14,  # total number of request
      "sqs.SendMessage": 2,  # number of sqs.SendMessage requests
      "sqs.ReceiveMessage": 1,  # number of sqs.ReceiveMessage requests
      "sns.Publish": 1,  # number of sns.Publish requests
      "dynamodb.PutItem": 0,  # Number of dynamodb.PutItem requests
      "dynamodb.GetItem": 0,  # Number of dynamodb.GetItem requests
      "dynamodb.BatchWriteItem": 0,  # Number of dynamodb.BatchWriteItem requests
      "dynamodb.BatchGetItem": 0,  # Number of dynamodb.BatchGetItem requests
      "lambda.Invoke": 0  # Number of lambda.Invoke requests
    }
  ],
  "sqs": [
    {
      "queue": "arn:aws:sqs:us-east-1:000000000000:input-dead-letter-queue",  # Queue Arn
      "visible": 0,  # Currently visible messages. Means actively queued, and available for receive_message
      "invisible": 0,  # Number of invisible messages. They have been received, but not yet requeued or deleted.
      "delayed": 0  # Number of delayed messages. They have been added with a delay, after which they become visible.
    }
  ],
  "sns": [
    {
      "topic_arn": "arn:aws:sns:us-east-1:000000000000:localstack-topic",  # Topic Arn
      "published": 1,  # Number of published messages
      "delivered": 0,  # Number of messages which were delivered to its subscriptions
      "failed": 0  # Number of messages which delivers failed
    }
  ],
  "timestamp": 1704986115.3762584  # Timestamp of the metric payload
}
```

We provided a script which you can run either as an init script (as ready initialization hook: https://docs.localstack.cloud/references/init-hooks/, please make sure to run it asynchronously), or as a sidecar container, or letting it connect directly via published port in your LocalStack container.

You can invoke it like this:
```
./scripts/stream_metrics.sh [localstack endpoint] [output file]
```

If the parameters are not specified, it will assume the localstack endpoint to be `http://localhost:4566`, and the output file to be `output.log`.

The script will call the metrics endpoint every second, and log the metrics to the output file.

You can use the output file to aggregate the metrics, to debug performance issues.


## Lambda Event invocation traces

This use case of the extension does not provide an external endpoint but writes to a log file you can analyze after a run of your scenario.

The traces are written to `<volume>/cache/observability/traces-lambda-events/lambda-<id>.ndjson.log`.

Inside this files, you will find events looking like this:

```json
{"timestamp": 1705006379.2201867, "event": "enqueued", "request_id": "8b68aff6-4131-43be-a906-c859b6052f54", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-function", "failure_cause": null}
{"timestamp": 1705006379.2363904, "event": "submitted", "request_id": "8b68aff6-4131-43be-a906-c859b6052f54", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-function", "failure_cause": null}
{"timestamp": 1705006379.2365327, "event": "invoking", "request_id": "8b68aff6-4131-43be-a906-c859b6052f54", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-function", "failure_cause": null}
{"timestamp": 1705006379.9108858, "event": "successful", "request_id": "8b68aff6-4131-43be-a906-c859b6052f54", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-function", "failure_cause": null}
```

A single event has the following fields:

* `timestamp`: Unix timestamps in seconds
* `event`: The event the lambda invoke passes. More on that in a bit.
* `request_id`: The request id of the lambda event invoke. Uniquely identifies a lambda invocation.
* `lambda_arn`: The lambda arn which was invoked. Might include a qualifier, if the invocation specified one.
* `failure_cause`: Only in case the event is `failed` or `retry`. Cause of the failure or retry.

There are 6 possible events. Every lambda event invoke passes through 4 of them.

* `enqueued`: The invocation gets enqueued into the sqs queue. Every lambda has to pass through it.
* `submitted`: The invocation gets taken out of the queue and submitted for invocation. Every lambda has to pass through it.
* `invoking`: The invocation actually starts. Every lambda has to pass through it.
* `success`: The invocation was a success.
* `retry`: The invocation will be retried, since there was some error.
* `failed`: The invocation has finally failed. There will be no more retries.

Since these traces can get quite confusing, we created some simple tool to aggregate the data a bit, for further processing.
You can find it in "scripts/summarize_lambda_event_log.py". Please note that it requires `pandas` to be installed.

An invocation looks like this:

```
./scripts/summarize_lambda_event_log.py ~/volume/cache/observability/traces-lambda/lambda-<uuid>.ndjson.log
```

and will yield a result (on the above events) like this:

```
event                                                                                                                  enqueued                      invoking                     submitted                    successful
request_id                           lambda_arn
8b68aff6-4131-43be-a906-c859b6052f54 arn:aws:lambda:us-east-1:000000000000:function:test-function 2024-01-11 20:52:59.220186624 2024-01-11 20:52:59.236532736 2024-01-11 20:52:59.236390400 2024-01-11 20:52:59.910885888
```

You can see one line per event invocation, and the timestamp they "passed" each event, including the request id and the lambda arn.
With this information, you should be able to track where your invocations are going missing.
Missing events in this table will be shown as `NaN`.
If events are in the table multiple times, they will be aggregated as a comma separated list in the column for the event.

You can use this script as starting point for your analysis.

## Lambda SQS Event source mapping traces

Similar to the event invocation traces, we also provide traces for SQS event source mappings, and how the messages proceed through LocalStack.

The traces are written to `<volume>/cache/observability/traces-lambda-sqs/lambda-<id>.ndjson.log`.

Inside this files, you will find events looking like this:

```json
{"timestamp": 1705009138.683765, "event": "message_queued", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": null, "request_id": null, "failure_cause": null}
{"timestamp": 1705009139.6799114, "event": "message_dequeued", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": null, "failure_cause": null}
{"timestamp": 1705009139.6799738, "event": "invoke_queued", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "0d616a5e-2511-4c88-a7b2-de0f0a7161ed", "failure_cause": null}
{"timestamp": 1705009139.6801724, "event": "invoke", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "0d616a5e-2511-4c88-a7b2-de0f0a7161ed", "failure_cause": null}
{"timestamp": 1705009140.0882578, "event": "invoke_success", "message_id": "94c3e579-dd40-48a6-bfaa-5d1d04c79044", "event_source_arn": "arn:aws:sqs:us-east-1:000000000000:test-queue-a5d98750", "lambda_arn": "arn:aws:lambda:us-east-1:000000000000:function:test-lambda-perf-33b02082", "request_id": "0d616a5e-2511-4c88-a7b2-de0f0a7161ed", "failure_cause": null}
```

A single event has the following fields:

* `timestamp`: Unix timestamps in seconds
* `event`: The event the lambda ESM invoke passes. More on that in a bit.
* `message_id`: The message id of the SQS message processed at that event. Uniquely identifies an sqs message.
* `event_source_arn`: The arn of the source SQS queue, where the message was received from.
* `request_id`: The request id of the lambda SQS ESM invoke. Uniquely identifies a lambda invocation. May be set to `null`, if the message is not handled in an invocation context yet.
* `lambda_arn`: The lambda arn which was invoked. Is null if the event is `message_queued`, since the lambda of the ESM is not known at that point. Might include a qualifier, if the ESM specified one.
* `failure_cause`: Only in case the event is `failed` or `retry`. Cause of the failure or retry.

There are 7 possible events. Every lambda SQS ESM invoke passes through 5 of them.

* `message_queued`: The message was queued into a lambda SQS queue.
* `message_dequeued`: The message was received by the event source listener.
* `invoke_queued`: The message was translated into a lambda call and the call was queued.
* `invoke`: The lambda for the message is being invoked
* `invoke_success`: The lambda invoke for the message was successful.
* `invoke_error`: The lambda invoke for the message completed, but with some error. Usually these are function errors, timeouts etc.
* `invoke_exception`: The lambda invoke resulted into an internal error. Can happen if a lambda environment cannot start, or some other internal error happens.

For analysis of this events, we recommend altering the `./scripts/summarize_lambda_event_log.py` accordingly.