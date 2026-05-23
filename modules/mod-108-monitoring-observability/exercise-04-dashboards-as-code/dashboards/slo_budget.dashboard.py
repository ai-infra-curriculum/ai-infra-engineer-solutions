"""SLO error-budget dashboard."""
from grafanalib.core import (
    Dashboard, Graph, Row, Stat, Target, Templating, Template,
    PERCENT_UNIT_FORMAT,
)


PROM = "$datasource"
AVAIL_SLO = 0.995
LAT_SLO = 0.95


dashboard = Dashboard(
    title="iris-api · SLO budget",
    tags=["iris", "slo"],
    timezone="utc",
    refresh="1m",
    templating=Templating(list=[
        Template(name="datasource", type="datasource", query="prometheus"),
    ]),
    rows=[
        Row(panels=[
            Stat(title=f"Availability SLI (target {AVAIL_SLO*100:.1f}%)",
                 dataSource=PROM,
                 format=PERCENT_UNIT_FORMAT,
                 targets=[Target(expr='sli:availability:ratio_rate5m')],
                 gridPos={"h": 4, "w": 8, "x": 0, "y": 0}),
            Stat(title="Error budget remaining (30d)",
                 dataSource=PROM,
                 format=PERCENT_UNIT_FORMAT,
                 targets=[Target(expr=(
                     f'1 - ((1 - avg_over_time(sli:availability:ratio_rate5m[30d])) / {1 - AVAIL_SLO})'
                 ))],
                 gridPos={"h": 4, "w": 8, "x": 8, "y": 0}),
            Stat(title=f"Latency SLI (target {LAT_SLO*100:.0f}%)",
                 dataSource=PROM,
                 format=PERCENT_UNIT_FORMAT,
                 targets=[Target(expr='sli:latency:under_200ms_ratio_rate5m')],
                 gridPos={"h": 4, "w": 8, "x": 16, "y": 0}),
        ]),
        Row(panels=[
            Graph(title="Budget burn rate (1h, 6h)",
                  dataSource=PROM,
                  targets=[
                      Target(expr=f'(1 - avg_over_time(sli:availability:ratio_rate5m[1h])) / {1 - AVAIL_SLO}',
                             legendFormat="1h burn"),
                      Target(expr=f'(1 - avg_over_time(sli:availability:ratio_rate5m[6h])) / {1 - AVAIL_SLO}',
                             legendFormat="6h burn"),
                  ]),
        ]),
    ],
).auto_panel_ids()
