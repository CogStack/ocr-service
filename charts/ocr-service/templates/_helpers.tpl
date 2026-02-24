{{/*
Expand the name of the chart.
*/}}
{{- define "ocr-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ocr-service.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ocr-service.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "ocr-service.labels" -}}
helm.sh/chart: {{ include "ocr-service.chart" . }}
{{ include "ocr-service.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "ocr-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ocr-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "ocr-service.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ocr-service.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Parse KEY=VALUE lines from env files passed through `.Values.envFiles.contents`.
Supports comments, blank lines, and optional `export ` prefix.
*/}}
{{- define "ocr-service.envFromFilesMap" -}}
{{- $env := dict -}}
{{- if and .Values.envFiles.enabled .Values.envFiles.contents }}
{{- range $content := .Values.envFiles.contents }}
{{- range $line := splitList "\n" (toString $content) }}
{{- $trimmed := trim $line -}}
{{- if and $trimmed (not (hasPrefix "#" $trimmed)) (contains "=" $trimmed) }}
{{- $parts := regexSplit "=" $trimmed 2 -}}
{{- if eq (len $parts) 2 }}
{{- $rawKey := trim (index $parts 0) -}}
{{- $key := $rawKey -}}
{{- if hasPrefix "export " $rawKey }}
{{- $key = trim (trimPrefix "export " $rawKey) -}}
{{- end }}
{{- if regexMatch "^[A-Za-z_][A-Za-z0-9_]*$" $key }}
{{- $value := trim (index $parts 1) -}}
{{- if and (hasPrefix "\"" $value) (hasSuffix "\"" $value) }}
{{- $value = trimSuffix "\"" (trimPrefix "\"" $value) -}}
{{- else if and (hasPrefix "'" $value) (hasSuffix "'" $value) }}
{{- $value = trimSuffix "'" (trimPrefix "'" $value) -}}
{{- end }}
{{- $_ := set $env $key $value -}}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- toYaml $env -}}
{{- end }}

{{/*
Merge chart env values with optional parsed env-file values.
When env files are enabled, env-file values override `.Values.env`.
*/}}
{{- define "ocr-service.mergedEnvMap" -}}
{{- $baseEnv := .Values.env | default dict -}}
{{- $envFromFiles := include "ocr-service.envFromFilesMap" . | fromYaml | default dict -}}
{{- $merged := dict -}}
{{- if .Values.envFiles.enabled }}
{{- $merged = mergeOverwrite $merged $baseEnv $envFromFiles -}}
{{- else }}
{{- $merged = mergeOverwrite $merged $baseEnv -}}
{{- end }}
{{- toYaml $merged -}}
{{- end }}
