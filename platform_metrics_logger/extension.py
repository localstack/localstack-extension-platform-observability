import json
import resource
import threading
import time

from localstack.extensions.api import Extension, http, aws
from localstack.utils.scheduler import Scheduler


class RequestCounter:
    def __init__(self, service_request_filter: list = None):
        self.service_request_filter = service_request_filter or []
        self.metrics = dict()
        self.clear()

    def clear(self):
        self.metrics.clear()
        self.metrics["total"] = 0
        for key in self.service_request_filter:
            self.metrics[key] = 0

    def on_request(self, chain: aws.HandlerChain, context: aws.RequestContext, response: http.Response):
        self.metrics["total"] += 1
        if context.service and context.operation:
            key = f"{context.service.service_name}.{context.operation.name}"
            if key in self.service_request_filter:
                self.metrics[f"{context.service.service_name}.{context.operation.name}"] += 1


class ServiceMetrics:
    def __init__(self):
        self.mutex = threading.RLock()

    def update_sqs(self, response: dict):
        from localstack.services.sqs.models import sqs_stores, FifoQueue, StandardQueue
        response["sqs_queues"] = 0
        response["sqs_queued_messages"] = 0
        response["sqs_inflight_messages"] = 0

        for _, _, store in sqs_stores.iter_stores():
            response["sqs_queues"] += len(store.queues)

            for queue in store.queues.values():
                response["sqs_inflight_messages"] += len(queue.inflight)
                if isinstance(queue, StandardQueue):
                    response["sqs_queued_messages"] += queue.visible.qsize()
                if isinstance(queue, FifoQueue):
                    for message_group in queue.message_groups.values():
                        response["sqs_queued_messages"] += len(message_group.messages)

    def update_lambda(self, response: dict):
        response['lambda_functions'] = 0
        from localstack.services.lambda_.invocation.lambda_service import lambda_stores

        for _, _, store in lambda_stores.iter_stores():
            response["lambda_functions"] += len(store.functions)

    def update(self, response: dict):
        self.update_sqs(response)
        self.update_lambda(response)

    def as_dict(self):
        result = {}
        self.update(result)
        return result


class MetricsLogger:
    def __init__(
            self,
            request_counter: RequestCounter,
            service_metrics: ServiceMetrics,
    ):
        self.request_counter = request_counter
        self.service_metrics = service_metrics

    def log(self):
        metrics = {
            "timestamp": int(time.time() * 100) / 100,
            "requests": dict(self.request_counter.metrics),
            "service_metrics": self.service_metrics.as_dict(),
            "active_thread_count": threading.active_count(),
            "max_rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        }

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
        self.service_metrics = ServiceMetrics()
        self.logger = MetricsLogger(
            self.request_counter,
            self.service_metrics,
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
