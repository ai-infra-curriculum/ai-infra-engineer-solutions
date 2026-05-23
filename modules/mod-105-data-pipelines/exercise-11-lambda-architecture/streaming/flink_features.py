"""PyFlink: 5-minute tumbling window per user_id, writes to Redis."""
from __future__ import annotations

from pyflink.common import Configuration, Duration, Types, WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment, TimeCharacteristic
from pyflink.datastream.connectors.kafka import KafkaSource
from pyflink.datastream.window import TumblingEventTimeWindows


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_stream_time_characteristic(TimeCharacteristic.EventTime)

    src = (KafkaSource.builder()
           .set_bootstrap_servers("kafka:9092")
           .set_topics("events.v1")
           .set_group_id("flink-feature-extractor")
           .set_starting_offsets("latest")
           .build())

    watermarks = (WatermarkStrategy
                  .for_bounded_out_of_orderness(Duration.of_seconds(30))
                  .with_idleness(Duration.of_minutes(1)))

    stream = env.from_source(src, watermarks, "kafka")

    (stream
     .map(lambda raw: parse_event(raw), output_type=Types.ROW([Types.STRING(), Types.LONG()]))
     .key_by(lambda r: r[0])                       # user_id
     .window(TumblingEventTimeWindows.of(Duration.of_minutes(5)))
     .reduce(lambda a, b: (a[0], a[1] + b[1]))     # sum clicks
     .map(lambda r: write_redis(r[0], r[1])))

    env.execute("user-5min-clicks")


def parse_event(raw):
    import json
    e = json.loads(raw)
    return (e["user_id"], 1 if e["event_type"] == "click" else 0)


def write_redis(user_id, clicks):
    # Real code: connect once, use a sink. Sketch:
    print(f"REDIS SET features:{user_id}:clicks_5m {clicks}")


if __name__ == "__main__":
    main()
