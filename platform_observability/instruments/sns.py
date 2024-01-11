from collections import defaultdict
from typing import Iterable

from localstack.services.sns import publisher
from localstack.services.sns.models import SnsMessage, SnsSubscription
from localstack.services.sns.publisher import (
    PublishDispatcher,
    SnsBatchPublishContext,
    SnsPublishContext,
)
from localstack.utils.patch import Patches

from platform_observability.instruments import Channel, Instrument


class TopicStatistics(Instrument):
    def __init__(self):
        self.topic_publish_count = defaultdict(lambda: 0)
        self.topic_delivery_count = defaultdict(lambda: 0)
        self.topic_delivery_failed_count = defaultdict(lambda: 0)

    def iter_topic_arns(self) -> Iterable[str]:
        topics = set(self.topic_publish_count.keys())
        yield from topics

    def measure_and_report(self, channel: Channel) -> None:
        for topic_arn in self.iter_topic_arns():
            channel.put(
                {
                    "topic_arn": topic_arn,
                    "published": self.topic_publish_count[topic_arn],
                    "delivered": self.topic_delivery_count[topic_arn],
                    "failed": self.topic_delivery_failed_count[topic_arn],
                }
            )

    def patches(self) -> Patches:
        topic_publish_count = self.topic_publish_count
        topic_delivery_count = self.topic_delivery_count
        topic_delivery_failed_count = self.topic_delivery_failed_count

        def _log_publish_to_topic(fn, self, ctx: SnsPublishContext, topic_arn: str):
            topic_publish_count[topic_arn] += 1
            return fn(self, ctx, topic_arn)

        def _log_publish_batch_to_topic(fn, self, ctx: SnsBatchPublishContext, topic_arn: str):
            topic_publish_count[topic_arn] += len(ctx.messages)
            return fn(self, ctx, topic_arn)

        def _log_store_delivery_log(
            fn,
            message_context: SnsMessage,
            subscriber: SnsSubscription,
            success: bool,
            topic_attributes: dict[str, str] = None,
            delivery: dict = None,
        ):
            topic_arn = subscriber["TopicArn"]
            if success:
                topic_delivery_count[topic_arn] += 1
            else:
                topic_delivery_failed_count[topic_arn] += 1

            return fn(message_context, subscriber, success, topic_attributes, delivery)

        patches = Patches()
        patches.function(PublishDispatcher.publish_to_topic, _log_publish_to_topic)
        patches.function(PublishDispatcher.publish_batch_to_topic, _log_publish_batch_to_topic)
        patches.function(publisher.store_delivery_log, _log_store_delivery_log)
        return patches
