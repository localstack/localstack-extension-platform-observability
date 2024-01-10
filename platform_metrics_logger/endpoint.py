import time

from localstack.http import route
from requests import Request

from .instruments.core import AggregatingInstrument, Instrument, ListCollector
from .instruments.sqs import QueueStatistics


class MetricsEndpoint:
    def __init__(self, instruments: dict[str, Instrument]):
        self.instruments = instruments

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
        instrument = QueueStatistics()
        collector = ListCollector()
        instrument.measure_and_report(collector)
        return {"queues": collector.records}
