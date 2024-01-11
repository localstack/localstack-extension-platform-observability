import logging
import threading
import time
from typing import Callable, NamedTuple, Optional

from localstack.aws.api.lambda_ import InvocationType
from localstack.services.lambda_.event_source_listeners.adapters import EventSourceAsfAdapter
from localstack.services.lambda_.event_source_listeners.event_source_listener import (
    EventSourceListener,
)
from localstack.services.lambda_.event_source_listeners.sqs_event_source_listener import (
    SQSEventSourceListener,
)
from localstack.services.lambda_.invocation.lambda_service import LambdaService
from localstack.services.sqs.models import FifoQueue, SqsMessage, StandardQueue
from localstack.utils.patch import Patches

LOG = logging.getLogger(__name__)


class LambdaSQSEventSourceEvent(NamedTuple):
    timestamp: float
    event: str
    """
    Event types are:
     - message_queued: message was added to the queue associated with an event source listener
     - message_dequeued: message was received by the event source listener
     - invoke_queued: the message was translated into a lambda call and the call was queued
     - invoke: the lambda is being invoked
     - invoke_success: invoke was successful
     - invoke_error: invoke completed but there was an error
     - invoke_exception: there was an exception while trying to invoke
    """
    message_id: str
    event_source_arn: str
    lambda_arn: str | None = None
    request_id: str | None = None
    failure_cause: str | None = None


class LambdaSQSEventSourceTracer:
    records: list[LambdaSQSEventSourceEvent]

    def __init__(self):
        self.records = []
        self.mutex = threading.RLock()
        self.queues = set()

    def flush(self) -> list[LambdaSQSEventSourceEvent]:
        with self.mutex:
            records = list(self.records)
            self.records.clear()
            return records

    def _register_queue_arn(self, sqs_queue_arn: str):
        self.queues.add(sqs_queue_arn)

    def _record_invocation(
        self,
        event: str,
        event_source_arn: str,
        message_id: str,
        lambda_arn: str | None = None,
        request_id: str | None = None,
        failure_cause: str | None = None,
    ):
        event = LambdaSQSEventSourceEvent(
            timestamp=time.time(),
            event=event,
            event_source_arn=event_source_arn,
            message_id=message_id,
            request_id=request_id,
            lambda_arn=lambda_arn,
            failure_cause=failure_cause,
        )
        with self.mutex:
            self.records.append(event)

    def patches(self) -> Patches:
        record_invocation = self._record_invocation
        tracer = self

        def _log_process_messages_for_event_source(fn, self, source, messages):
            for message in messages:
                record_invocation(
                    event="message_dequeued",
                    event_source_arn=source["EventSourceArn"],
                    message_id=message["MessageId"],
                    lambda_arn=source["FunctionArn"],
                    request_id=None,
                )
            return fn(self, source, messages)

        def _log_adapter_invoke_async(
            fn,
            self,
            request_id: str,
            function_arn: str,
            context: dict,
            payload: dict,
            invocation_type: InvocationType,
            callback: Optional[Callable] = None,
        ):
            for message in payload.get("Records", []):
                if "sqs" not in message.get("eventSourceARN", ""):
                    return

                record_invocation(
                    event="invoke_queued",
                    event_source_arn=message.get("eventSourceARN"),
                    message_id=message.get("messageId"),
                    lambda_arn=function_arn,
                    request_id=request_id,
                )

            return fn(self, request_id, function_arn, context, payload, invocation_type, callback)

        def _log_adapter_invoke_sync(
            fn,
            self,
            request_id: str,
            function_arn: str,
            context: dict,
            payload: dict,
            invocation_type: InvocationType,
            callback: Optional[Callable] = None,
        ):
            for message in payload.get("Records", []):
                if "sqs" not in message.get("eventSourceARN", ""):
                    return

                record_invocation(
                    message_id=message.get("messageId"),
                    event_source_arn=message.get("eventSourceARN"),
                    lambda_arn=function_arn,
                    request_id=request_id,
                    event="invoke",
                )

            def _callback(*args, **kwargs):
                event = "invoke_success" if not kwargs.get("error") else "invoke_error"
                error_cause = str(kwargs.get("error")) if kwargs.get("error") else None

                for message in payload.get("Records", []):
                    if "sqs" not in message.get("eventSourceARN", ""):
                        return

                    record_invocation(
                        message_id=message.get("messageId"),
                        event_source_arn=message.get("eventSourceARN"),
                        lambda_arn=function_arn,
                        request_id=request_id,
                        event=event,
                        failure_cause=error_cause,
                    )

                if callback:
                    return callback(*args, **kwargs)

            try:
                return fn(
                    self, request_id, function_arn, context, payload, invocation_type, _callback
                )
            except Exception as e:
                for message in payload.get("Records", []):
                    if "sqs" not in message.get("eventSourceARN", ""):
                        return

                    record_invocation(
                        message_id=message.get("messageId"),
                        event_source_arn=message.get("eventSourceARN"),
                        lambda_arn=function_arn,
                        request_id=request_id,
                        event="invoke_exception",
                        failure_cause=e.__class__.__name__,
                    )

        # LambdaEventManager patches
        def _log_lambda_invoke(
            fn,
            self,
            function_name: str,
            qualifier: str,
            region: str,
            account_id: str,
            invocation_type: InvocationType | None,
            client_context: Optional[str],
            request_id: str,
            payload: bytes | None,
        ):
            return fn(
                self,
                function_name,
                qualifier,
                region,
                account_id,
                invocation_type,
                client_context,
                request_id,
                payload,
            )

        def _log_start_listeners_for_asf(
            fn, event_source_mapping: dict, lambda_service: LambdaService
        ):
            source_arn = event_source_mapping.get("EventSourceArn") or ""
            if ":sqs:" in source_arn:
                tracer._register_queue_arn(source_arn)

            return fn(event_source_mapping, lambda_service)

        def _log_put_message(fn, self, message: SqsMessage):
            if self.arn in tracer.queues:
                record_invocation(
                    message_id=message.message_id,
                    event_source_arn=self.arn,
                    lambda_arn=None,
                    request_id=None,
                    event="message_queued",
                )

            return fn(self, message)

        patches = Patches()

        patches.function(
            FifoQueue._put_message,
            _log_put_message,
        )
        patches.function(
            StandardQueue._put_message,
            _log_put_message,
        )

        patches.function(
            EventSourceListener.start_listeners_for_asf,
            _log_start_listeners_for_asf,
        )
        patches.function(
            SQSEventSourceListener._process_messages_for_event_source,
            _log_process_messages_for_event_source,
        )
        patches.function(
            EventSourceAsfAdapter._invoke_async,
            _log_adapter_invoke_async,
        )
        patches.function(
            EventSourceAsfAdapter._invoke_sync,
            _log_adapter_invoke_sync,
        )

        patches.function(
            LambdaService.invoke,
            _log_lambda_invoke,
        )
        return patches
