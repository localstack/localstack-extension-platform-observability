import json
import logging
import threading
from pathlib import Path
from typing import NamedTuple, Protocol

LOG = logging.getLogger(__name__)


class TraceCollector(Protocol):
    def flush(self) -> list[NamedTuple]:
        ...


class TraceFileLogger:
    def __init__(self, file: Path, tracer: TraceCollector):
        self.file = file
        self.tracer = tracer
        self.mutex = threading.RLock()

    def init_file(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.touch(exist_ok=True)

    def close(self):
        self.flush()

    def flush(self):
        with self.mutex:
            records = self.tracer.flush()
            if not records:
                return

            try:
                with self.file.open("a") as fd:
                    records = [json.dumps(record._asdict()) + "\n" for record in records]
                    fd.writelines(records)
            except Exception:
                LOG.exception("error while flushing to %s", self.file)
