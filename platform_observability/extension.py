import logging
import threading
from pathlib import Path

from localstack import config
from localstack.aws.chain import CompositeHandler, CompositeResponseHandler
from localstack.extensions.api import Extension
from localstack.http import Router
from localstack.utils.analytics import get_session_id
from localstack.utils.scheduler import Scheduler

from .endpoint import MetricsEndpoint
from .instruments.aggregate import RequestCounter, SystemMetrics
from .instruments.sns import TopicStatistics
from .instruments.sqs import QueueStatistics
from .tracing.lambda_ import LambdaLifecycleTracer
from .tracing.lambda_sqs import LambdaSQSEventSourceTracer
from .tracing.logging import TraceFileLogger

LOG = logging.getLogger(__name__)


class ObservabilityExtension(Extension):
    name = "localstack-extension-platform-observability"

    def __init__(self):
        logging.getLogger("platform_observability").setLevel(
            logging.DEBUG if config.DEBUG else logging.INFO
        )

        # set up instruments
        self.request_counter = RequestCounter(
            # TODO: make configurable
            service_request_filter=[
                "sqs.SendMessage",
                "sqs.ReceiveMessage",
                "sns.Publish",
                "dynamodb.PutItem",
                "dynamodb.GetItem",
                "dynamodb.BatchWriteItem",
                "dynamodb.BatchGetItem",
                "lambda.Invoke",
            ]
        )
        self.system_metrics = SystemMetrics()
        self.topic_statistics = TopicStatistics()
        self.queue_statistics = QueueStatistics()
        self.lambda_tracer = LambdaLifecycleTracer()
        self.lambda_sqs_event_source_tracer = LambdaSQSEventSourceTracer()

        # /metrics endpoint
        self.metrics_endpoint = MetricsEndpoint(
            {
                "system": self.system_metrics,
                "gateway": self.request_counter,
                "sqs": self.queue_statistics,
                "sns": self.topic_statistics,
            }
        )

        # lambda trace logs
        lambda_trace_file = Path(
            config.dirs.cache,
            "observability/traces-lambda-events",
            f"lambda-{get_session_id()}.ndjson.log",
        )
        lambda_sqs_trace_file = Path(
            config.dirs.cache,
            "observability/traces-lambda-sqs",
            f"lambda-sqs-{get_session_id()}.ndjson.log",
        )

        self.loggers = [
            TraceFileLogger(lambda_trace_file, self.lambda_tracer),
            TraceFileLogger(lambda_sqs_trace_file, self.lambda_sqs_event_source_tracer),
        ]

        self.scheduler = Scheduler()
        self.interval = 1

    def on_extension_load(self):
        self.topic_statistics.patches().apply()
        self.lambda_tracer.patches().apply()
        self.lambda_sqs_event_source_tracer.patches().apply()
        LOG.info("Metrics extension is loaded")

    def on_platform_start(self):
        LOG.info("Starting trace logging")
        for logger in self.loggers:
            logger.init_file()

        for logger in self.loggers:
            self.scheduler.schedule(func=logger.flush, period=self.interval)

        threading.Thread(target=self.scheduler.run, daemon=True, name="trace-logger").start()

    def on_platform_shutdown(self):
        self.scheduler.close()
        for logger in self.loggers:
            logger.close()

    def update_gateway_routes(self, router: Router):
        router.add(self.metrics_endpoint)

    def update_request_handlers(self, handlers: CompositeHandler):
        handlers.append(self.request_counter.on_request)
        pass

    def update_response_handlers(self, handlers: CompositeResponseHandler):
        pass
