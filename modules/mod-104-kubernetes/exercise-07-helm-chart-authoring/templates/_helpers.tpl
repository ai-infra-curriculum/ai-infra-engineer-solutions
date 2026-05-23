{{- define "iris-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "iris-api.fullname" -}}
{{- default (include "iris-api.name" .) .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "iris-api.labels" -}}
app.kubernetes.io/name: {{ include "iris-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "iris-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "iris-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
