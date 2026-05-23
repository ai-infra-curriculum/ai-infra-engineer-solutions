"""ML drift dashboard."""
from grafanalib.core import (
    Dashboard, Graph, Row, Stat, Target, Templating, Template,
    PERCENT_UNIT_FORMAT,
)


PROM = "$datasource"


dashboard = Dashboard(
    title="iris-api · ml drift",
    tags=["iris", "ml", "drift"],
    timezone="utc",
    refresh="1m",
    templating=Templating(list=[
        Template(name="datasource", type="datasource", query="prometheus"),
        Template(name="model_version", dataSource=PROM,
                  query="label_values(model_info, version)"),
    ]),
    rows=[
        Row(panels=[
            Stat(title="PSI (population stability)", dataSource=PROM,
                 targets=[Target(expr='avg(model_drift_psi{model_version="$model_version"})')],
                 gridPos={"h": 4, "w": 8, "x": 0, "y": 0}),
            Stat(title="Prediction class drift %", dataSource=PROM,
                 format=PERCENT_UNIT_FORMAT,
                 targets=[Target(expr='model_class_distribution_kl{model_version="$model_version"}')],
                 gridPos={"h": 4, "w": 8, "x": 8, "y": 0}),
            Stat(title="Feature null rate", dataSource=PROM,
                 format=PERCENT_UNIT_FORMAT,
                 targets=[Target(expr='avg(feature_null_rate{model_version="$model_version"})')],
                 gridPos={"h": 4, "w": 8, "x": 16, "y": 0}),
        ]),
        Row(panels=[
            Graph(title="PSI by feature", dataSource=PROM,
                  targets=[Target(expr='model_drift_psi{model_version="$model_version"}',
                                  legendFormat="{{feature}}")]),
            Graph(title="Predicted-class distribution",
                  dataSource=PROM,
                  targets=[Target(expr='sum by (predicted_class) '
                                       '(rate(predictions_total{model_version="$model_version"}[5m]))',
                                  legendFormat="{{predicted_class}}")]),
        ]),
    ],
).auto_panel_ids()
