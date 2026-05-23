"""iris-api overview dashboard."""
from grafanalib.core import (
    Dashboard, Graph, Row, Stat, Target, Templating, Template, Annotations,
    Annotation, SECONDS_FORMAT, GAUGE_TYPE, OPS_FORMAT, PERCENT_UNIT_FORMAT,
)


PROM = "$datasource"


dashboard = Dashboard(
    title="iris-api · overview",
    tags=["iris", "api", "ml"],
    timezone="utc",
    refresh="30s",
    templating=Templating(list=[
        Template(name="datasource", type="datasource", query="prometheus"),
        Template(name="namespace", dataSource=PROM,
                  query="label_values(kube_namespace_status_phase, namespace)"),
        Template(name="service", dataSource=PROM,
                  query='label_values(up{namespace="$namespace"}, job)'),
    ]),
    annotations=Annotations(list=[
        Annotation(name="deploys", dataSource=PROM,
                    expr='changes(kube_deployment_metadata_generation{namespace="$namespace"}[1m]) > 0'),
    ]),
    rows=[
        Row(panels=[
            Stat(title="RPS", dataSource=PROM,
                 targets=[Target(expr='sum(rate(http_requests_total{job="$service"}[5m]))')],
                 format=OPS_FORMAT, gridPos={"h": 4, "w": 6, "x": 0, "y": 0}),
            Stat(title="Error %", dataSource=PROM, format=PERCENT_UNIT_FORMAT,
                 targets=[Target(expr=(
                     'sum(rate(http_requests_total{job="$service",status=~"5.."}[5m])) '
                     '/ sum(rate(http_requests_total{job="$service"}[5m]))'))],
                 gridPos={"h": 4, "w": 6, "x": 6, "y": 0}),
            Stat(title="p95 latency", dataSource=PROM, format=SECONDS_FORMAT,
                 targets=[Target(expr=(
                     'histogram_quantile(0.95, sum by (le) '
                     '(rate(http_request_duration_seconds_bucket{job="$service"}[5m])))'))],
                 gridPos={"h": 4, "w": 6, "x": 12, "y": 0}),
            Stat(title="active pods", dataSource=PROM, type=GAUGE_TYPE,
                 targets=[Target(expr='count(up{job="$service"} == 1)')],
                 gridPos={"h": 4, "w": 6, "x": 18, "y": 0}),
        ]),
        Row(panels=[
            Graph(title="RPS by path", dataSource=PROM,
                  targets=[Target(expr='sum by (path) (rate(http_requests_total{job="$service"}[1m]))',
                                  legendFormat="{{path}}")]),
            Graph(title="latency quantiles", dataSource=PROM,
                  targets=[
                      Target(expr='histogram_quantile(0.5, sum by (le) '
                                  '(rate(http_request_duration_seconds_bucket{job="$service"}[5m])))',
                             legendFormat="p50"),
                      Target(expr='histogram_quantile(0.95, sum by (le) '
                                  '(rate(http_request_duration_seconds_bucket{job="$service"}[5m])))',
                             legendFormat="p95"),
                      Target(expr='histogram_quantile(0.99, sum by (le) '
                                  '(rate(http_request_duration_seconds_bucket{job="$service"}[5m])))',
                             legendFormat="p99"),
                  ]),
        ]),
    ],
).auto_panel_ids()
