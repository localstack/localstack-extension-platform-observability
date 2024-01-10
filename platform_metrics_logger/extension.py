import json

from localstack.extensions.api import Extension, aws, http
from localstack.http import route
from localstack.utils.scheduler import Scheduler

from .instruments import Instrument, collect_instrument_data
from .instruments.aggregate import RequestCounter, ServiceMetrics, SystemMetrics


class MetricsJsonPrinter:
    def __init__(self, instruments: list[Instrument]):
        self.instruments = instruments

    def log(self):
        print(json.dumps(collect_instrument_data(self.instruments)))


class MetricsEndpoint(Extension):
    def __init__(self, instruments: list[Instrument]):
        self.instruments = instruments

    @route("/_extension/metrics/all")
    def get_all(self, request: http.Request):
        return collect_instrument_data(self.instruments)


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
        self.aggregate_endpoint = MetricsEndpoint(
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
        # self.scheduler.schedule(func=self.logger.log, period=self.interval)
        # threading.Thread(target=self.scheduler.run, daemon=True, name="metric-logger").start()

    def on_platform_ready(self):
        print("MyExtension: localstack is running")

    def on_platform_shutdown(self):
        self.scheduler.close()

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        router.add(self.aggregate_endpoint)

    def update_request_handlers(self, handlers: aws.CompositeHandler):
        handlers.append(self.request_counter.on_request)
        pass

    def update_response_handlers(self, handlers: aws.CompositeResponseHandler):
        pass
