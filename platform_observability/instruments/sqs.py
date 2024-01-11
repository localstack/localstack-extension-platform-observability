import time
from typing import Iterable

from localstack.services.sqs.models import FifoQueue, SqsQueue, StandardQueue, sqs_stores

from platform_observability.instruments import Channel, Instrument


class QueueStatistics(Instrument):
    def iter_queues(self) -> Iterable[SqsQueue]:
        for _, _, store in sqs_stores.iter_stores():
            for queue in store.queues.values():
                yield queue

    def measure_and_report(self, channel: Channel) -> None:
        for queue in self.iter_queues():
            delayed = len(queue.delayed)
            if isinstance(queue, StandardQueue):
                visible = queue.visible.qsize()
                invisible = len(queue.inflight)
            elif isinstance(queue, FifoQueue):
                visible = 0
                invisible = 0

                for message_group in queue.message_group_queue.queue:
                    visible += len(message_group.messages)

                for message_group in queue.inflight_groups:
                    invisible += len(message_group.messages)

            else:
                raise ValueError("unknown queue type")

            channel.put(
                {
                    "queue": queue.arn,
                    "visible": visible,
                    "invisible": invisible,
                    "delayed": delayed,
                }
            )
