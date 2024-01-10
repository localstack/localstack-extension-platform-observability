import json
import threading
import time

from localstack.extensions.api import Extension, aws, http
from localstack.utils.scheduler import Scheduler

from .instruments import Instrument, RequestCounter, ServiceMetrics, SystemMetrics


class MetricsJsonPrinter:
    def __init__(self, instruments: list[Instrument]):
        self.instruments = instruments

    def log(self):
        metrics = {
            "timestamp": int(time.time() * 100) / 100,
        }

        for instrument in self.instruments:
            metrics[instrument.name] = dict()
            instrument.measure_and_report(metrics[instrument.name])

        print(json.dumps(metrics))


class MyExtension(Extension):
    name = "localstack-extension-platform-metrics-logger"

    def __init__(self):
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

        self.logger = MetricsJsonPrinter(
            [
                self.request_counter,
                self.service_metrics,
                self.system_metrics,
            ]
        )

        self.scheduler = Scheduler()
        self.interval = 1

    def on_extension_load(self):
        print("MyExtension: extension is loaded")

    def on_platform_start(self):
        print("MyExtension: localstack is starting")
        self.scheduler.schedule(func=self.logger.log, period=self.interval)
        threading.Thread(target=self.scheduler.run, daemon=True, name="metric-logger").start()

    def on_platform_ready(self):
        print("MyExtension: localstack is running")

    def on_platform_shutdown(self):
        self.scheduler.close()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        pass

    def update_request_handlers(self, handlers: aws.CompositeHandler):
        handlers.append(self.request_counter.on_request)
        pass

    def update_response_handlers(self, handlers: aws.CompositeResponseHandler):
        pass
