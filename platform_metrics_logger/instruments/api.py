import time


class Instrument:
    name: str

    def measure_and_report(self, result: dict) -> None:
        raise NotImplementedError


def collect_instrument_data(instruments: list[Instrument]) -> dict:
    metrics = {
        "timestamp": int(time.time() * 100) / 100,
    }

    for instrument in instruments:
        metrics[instrument.name] = dict()
        instrument.measure_and_report(metrics[instrument.name])

    return metrics
