"""Feast feature definitions."""
from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Int64, String


user = Entity(name="user", join_keys=["user_id"])

clicks_source = FileSource(
    name="clicks_source",
    path="data/clicks.parquet",
    timestamp_field="event_ts",
)

purchases_source = FileSource(
    name="purchases_source",
    path="data/purchases.parquet",
    timestamp_field="event_ts",
)

user_recency_fv = FeatureView(
    name="user_recency",
    entities=[user],
    ttl=timedelta(days=7),
    schema=[
        Field(name="clicks_7d", dtype=Int64),
        Field(name="last_event_category", dtype=String),
    ],
    source=clicks_source,
)

user_purchase_fv = FeatureView(
    name="user_purchase",
    entities=[user],
    ttl=timedelta(days=30),
    schema=[
        Field(name="purchases_30d", dtype=Int64),
        Field(name="ltv", dtype=Float32),
    ],
    source=purchases_source,
)
