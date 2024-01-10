import json
import logging
import threading
import time
from pathlib import Path
from typing import NamedTuple

from localstack.services.lambda_.invocation import event_manager
from localstack.services.lambda_.invocation.event_manager import (
    EventInvokeConfig,
    InvocationResult,
    SQSInvocation,
)
from localstack.services.lambda_.invocation.lambda_models import Invocation
from localstack.utils.patch import Patch, Patches

LOG = logging.getLogger(__name__)


class LambdaLifecycleEvent(NamedTuple):
    timestamp: float
    event: str
    request_id: str
    lambda_arn: str
    failure_cause: str | None = None


class LambdaLifecycleLogger:
    def __init__(self, file: Path, tracer: "LambdaLifecycleTracer"):
        self.file = file
        self.tracer = tracer
        self.mutex = threading.RLock()

    def close(self):
        self.flush()

    def flush(self):
        with self.mutex:
            records = self.tracer.flush()
            if not records:
                return

            try:
                with self.file.open("a") as fd:
                    records = [json.dumps(record._asdict()) + "\n" for record in records]
                    fd.writelines(records)
            except Exception:
                LOG.exception("error while flushing to %s", self.file)


class LambdaLifecycleTracer:
    records: list[LambdaLifecycleEvent]

    def __init__(self):
        self.records = []
        self.mutex = threading.RLock()

    def flush(self) -> list[LambdaLifecycleEvent]:
        with self.mutex:
            records = list(self.records)
            self.records.clear()
            return records

    def _record_invocation(
        self, event_name: str, invocation: Invocation, failure_cause: str = None
    ):
        event = LambdaLifecycleEvent(
            timestamp=time.time(),
            event=event_name,
            request_id=invocation.request_id,
            lambda_arn=invocation.invoked_arn,
            failure_cause=failure_cause,
        )
        with self.mutex:
            self.records.append(event)

    def patches(self) -> Patches:
        record_invocation = self._record_invocation

        # LambdaEventManager patches
        def _log_enqueue_event(fn, self, invocation: Invocation):
            record_invocation("enqueued", invocation)
            return fn(self, invocation)

        # Poller patches
        def _poller_init(fn, self, *args, **kwargs):
            # this patch just exists to patch invoker_pool
            fn(self, *args, **kwargs)
            Patch.function(self.invoker_pool.submit, _log_invoker_pool_submit).apply()

        def _log_invoker_pool_submit(self, fn, handle_message, message: dict):
            sqs_invocation = SQSInvocation.decode(message["Body"])
            record_invocation("submitted", sqs_invocation.invocation)
            return fn(handle_message, message)

        def _log_handle_message(fn, self, message: dict):
            sqs_invocation = SQSInvocation.decode(message["Body"])
            record_invocation(
                "invoking",
                sqs_invocation.invocation,
            )
            return fn(self, message)

        def _log_process_success_destination(
            fn,
            self,
            sqs_invocation: SQSInvocation,
            invocation_result: InvocationResult,
            event_invoke_config: EventInvokeConfig | None,
        ) -> None:
            record_invocation(
                "successful",
                sqs_invocation.invocation,
            )
            return fn(self, sqs_invocation, invocation_result, event_invoke_config)

        def _log_process_failure_destination(
            fn,
            self,
            sqs_invocation: SQSInvocation,
            invocation_result: InvocationResult,
            event_invoke_config: EventInvokeConfig | None,
            failure_cause: str,
        ) -> None:
            record_invocation(
                "failed",
                sqs_invocation.invocation,
                failure_cause=failure_cause,
            )
            return fn(self, sqs_invocation, invocation_result, event_invoke_config)

        def _log_process_throttles_and_system_errors(
            fn, self, sqs_invocation: SQSInvocation, error: Exception
        ):
            record_invocation(
                "retry",
                sqs_invocation.invocation,
                failure_cause=type(error).__name__,
            )
            return fn(self, sqs_invocation, error)

        return Patches(
            [
                Patch.function(
                    event_manager.LambdaEventManager.enqueue_event,
                    _log_enqueue_event,
                ),
                Patch.function(
                    event_manager.Poller.__init__,
                    _poller_init,
                ),
                Patch.function(
                    event_manager.Poller.handle_message,
                    _log_handle_message,
                ),
                Patch.function(
                    event_manager.Poller.process_success_destination,
                    _log_process_success_destination,
                ),
                # Patch.function(
                #     event_manager.Poller.process_throttles_and_system_errors,
                #     _log_process_throttles_and_system_errors,
                # ),
                Patch.function(
                    event_manager.Poller.process_failure_destination,
                    _log_process_failure_destination,
                ),
            ]
        )
