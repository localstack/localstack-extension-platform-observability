import time

from localstack.http import Request, route
from werkzeug.exceptions import NotFound

from .instruments.core import AggregatingInstrument, Instrument, ListCollector
from .instruments.sns import TopicStatistics
from .instruments.sqs import QueueStatistics


class MetricsEndpoint:
    def __init__(self, instruments: dict[str, Instrument]):
        self.instruments = instruments

    @route("/_extension/observability/metrics")
    def get_metrics(self, request: Request):
        instrument_filter = request.args.getlist("instrument")

        instruments = self.instruments
        if instrument_filter:
            instruments = {k: v for k, v in instruments.items() if v in instrument_filter}

        aggregator = AggregatingInstrument(instruments, flatten=False)
        collector = ListCollector()
        aggregator.measure_and_report(collector)

        record = collector.records[0]
        record["timestamp"] = time.time()
        return record

    @route("/_extension/observability/metrics/<instrument>")
    def get_metrics_for_instrument(self, request: Request, instrument: str):
        collector = ListCollector()

        try:
            instrument_obj = self.instruments[instrument]
        except KeyError:
            raise NotFound(f"unknown instrument {instrument}")

        instrument_obj.measure_and_report(collector)
        return {"timestamp": time.time(), instrument: collector.records}
