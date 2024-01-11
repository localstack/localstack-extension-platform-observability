import json
from collections import defaultdict
from typing import Protocol

Record = dict


class Channel(Protocol):
    def put(self, record: Record):
        raise NotImplementedError


class Instrument:
    def measure_and_report(self, channel: Channel) -> None:
        raise NotImplementedError


class ListCollector:
    records: list[Record]

    def __init__(self):
        self.records = []

    def put(self, record: Record):
        self.records.append(record)


class _NamedAggregator:
    name: str
    record: dict

    def __init__(self):
        self.record = defaultdict(list)
        self.name = None

    def put(self, record):
        self.record[self.name].append(record)


class AggregatingInstrument(Instrument):
    instruments: dict[str, Instrument]

    def __init__(self, instruments: dict[str, Instrument], flatten: bool = True):
        self.instruments = instruments
        self.flatten = flatten

    def measure_and_report(self, channel: Channel) -> None:
        collector = _NamedAggregator()

        for name, instrument in self.instruments.items():
            collector.name = name
            instrument.measure_and_report(collector)

        record = dict(collector.record)
        if self.flatten:
            for k, v in collector.record.items():
                record[k] = v[0] if len(v) == 1 else v

        channel.put(record)


class JsonPrinter:
    def put(self, record: Record) -> None:
        print(json.dumps(record))
