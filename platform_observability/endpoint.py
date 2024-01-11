import time

from localstack.http import route
from requests import Request

from .instruments.core import AggregatingInstrument, Instrument, ListCollector
from .instruments.sns import TopicStatistics
from .instruments.sqs import QueueStatistics


class MetricsEndpoint:
    def __init__(
        self,
        instruments: dict[str, Instrument],
        queue_statistics: QueueStatistics,
        topic_statistics: TopicStatistics,
    ):
        self.instruments = instruments
        self.topic_statistics = topic_statistics
        self.queue_statistics = queue_statistics

    @route("/_extension/metrics/all")
    def get_all(self, request: Request):
        timestamp = time.time()
        aggregator = AggregatingInstrument(self.instruments)
        collector = ListCollector()
        aggregator.measure_and_report(collector)
        record = collector.records[0]
        record["timestamp"] = timestamp
        return record

    @route("/_extension/metrics/sqs")
    def get_sqs(self, request: Request):
        collector = ListCollector()
        self.queue_statistics.measure_and_report(collector)
        return {"queues": collector.records}

    @route("/_extension/metrics/sns")
    def get_sns(self, request: Request):
        collector = ListCollector()
        self.topic_statistics.measure_and_report(collector)
        return {"topics": collector.records}
