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
from .instruments.aggregate import RequestCounter, ServiceMetrics, SystemMetrics
from .instruments.lambda_ import LambdaLifecycleLogger, LambdaLifecycleTracer
from .instruments.sns import TopicStatistics
from .instruments.sqs import QueueStatistics

LOG = logging.getLogger(__name__)


class ObservabilityExtension(Extension):
    name = "localstack-extension-platform-observability"

    def __init__(self):
        logging.getLogger("platform_observability").setLevel(
            logging.DEBUG if config.DEBUG else logging.INFO
        )

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
        self.service_metrics = ServiceMetrics(
            # TODO: make configurable
        )
        self.system_metrics = SystemMetrics()
        self.lambda_tracer = LambdaLifecycleTracer()

        # /metrics endpoint
        self.topic_statistics = TopicStatistics()
        self.queue_statistics = QueueStatistics()
        self.endpoint = MetricsEndpoint(
            {
                "requests": self.request_counter,
                "service_metrics": self.service_metrics,
                "system_metrics": self.system_metrics,
            },
            queue_statistics=self.queue_statistics,
            topic_statistics=self.topic_statistics,
        )

        # lambda trace logs
        logs_file = Path(
            config.dirs.cache, "metrics/lambda-traces", f"{get_session_id()}.ndjson.log"
        )
        logs_file.parent.mkdir(parents=True, exist_ok=True)
        logs_file.touch(exist_ok=True)

        self.lambda_trace_logger = LambdaLifecycleLogger(logs_file, self.lambda_tracer)

        self.scheduler = Scheduler()
        self.interval = 1

    def on_extension_load(self):
        self.topic_statistics.patches().apply()
        self.lambda_tracer.patches().apply()
        LOG.info("Metrics extension is loaded")

    def on_platform_start(self):
        LOG.info("Starting metric scheduler")
        # self.scheduler.schedule(func=self.logger.log, period=self.interval)
        self.scheduler.schedule(func=self.lambda_trace_logger.flush, period=self.interval)
        threading.Thread(target=self.scheduler.run, daemon=True, name="metric-logger").start()

    def on_platform_shutdown(self):
        self.scheduler.close()

    def update_gateway_routes(self, router: Router):
        router.add(self.endpoint)

    def update_request_handlers(self, handlers: CompositeHandler):
        handlers.append(self.request_counter.on_request)
        pass

    def update_response_handlers(self, handlers: CompositeResponseHandler):
        pass
