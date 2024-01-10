import threading

from localstack.aws.api import RequestContext
from localstack.aws.chain import HandlerChain
from requests import Response

from .core import Channel, Instrument


class RequestCounter(Instrument):
    name = "requests"

    def __init__(self, service_request_filter: list = None):
        self.service_request_filter = service_request_filter or []
        self.metrics = dict()
        self.clear()

    def clear(self):
        self.metrics.clear()
        self.metrics["total"] = 0
        for key in self.service_request_filter:
            self.metrics[key] = 0

    def on_request(self, chain: HandlerChain, context: RequestContext, response: Response):
        self.metrics["total"] += 1
        if context.service and context.operation:
            key = f"{context.service.service_name}.{context.operation.name}"
            if key in self.service_request_filter:
                self.metrics[f"{context.service.service_name}.{context.operation.name}"] += 1

    def measure_and_report(self, channel: Channel) -> None:
        channel.put(self.metrics)


class ServiceMetrics(Instrument):
    name = "service_metrics"

    def update_sqs(self, response: dict):
        from localstack.services.sqs.models import FifoQueue, StandardQueue, sqs_stores

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
                    for message_group in queue.message_group_queue.queue:
                        response["sqs_queued_messages"] += len(message_group.messages)

    def update_lambda(self, response: dict):
        response["lambda_functions"] = 0
        from localstack.services.lambda_.invocation.lambda_service import lambda_stores

        for _, _, store in lambda_stores.iter_stores():
            response["lambda_functions"] += len(store.functions)

    def measure_and_report(self, channel: Channel):
        record = {}
        self.update_sqs(record)
        self.update_lambda(record)
        channel.put(record)


class SystemMetrics(Instrument):
    name = "system"

    def measure_and_report(self, channel: Channel) -> None:
        record = {
            "active_thread_count": threading.active_count(),
            "max_rss": threading.active_count(),
        }
        channel.put(record)
