{{/*
이름 헬퍼.

쿠버네티스 리소스 이름과 라벨 값의 상한이 둘 다 63자입니다. 여기서 한 번 자르고,
쓰는 쪽에서는 신경 쓰지 않게 합니다. 애플리케이션 ID(=릴리스 이름)를 30자 안쪽으로
잡으라는 권고가 여기서 나옵니다 — 차트가 붙이는 접미사까지 63자 안에 들어가야 합니다.
*/}}
{{- define "llm-tutorial.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "llm-tutorial.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "llm-tutorial.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "llm-tutorial.labels" -}}
helm.sh/chart: {{ include "llm-tutorial.chart" . }}
{{ include "llm-tutorial.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "llm-tutorial.selectorLabels" -}}
app.kubernetes.io/name: {{ include "llm-tutorial.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
LLM 키를 담은 Secret의 이름. 셋 다 아니면 빈 값이고, OpenBao도 안 쓰면
check-values.yaml이 렌더를 거부합니다.
*/}}
{{- define "llm-tutorial.secretName" -}}
{{- if .Values.runway.credentials.existingSecret -}}
{{- .Values.runway.credentials.existingSecret -}}
{{- else if .Values.runway.credentials.create -}}
{{- printf "%s-credentials" (include "llm-tutorial.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
CPU 리밋을 "코어 개수"로 바꿉니다. 스레드 풀 상한에 쓰입니다.

`500m`을 그대로 넘기면 500이 되어 정확히 반대 결과가 납니다 — 반 코어짜리 컨테이너가
스레드 500개를 띄웁니다. millicore는 1000으로 나누고, 최소 1을 보장합니다.
*/}}
{{- define "llm-tutorial.cpuThreads" -}}
{{- $cpu := .Values.resources.limits.cpu | toString -}}
{{- if hasSuffix "m" $cpu -}}
{{- $milli := $cpu | trimSuffix "m" | int -}}
{{- max 1 (div $milli 1000) -}}
{{- else -}}
{{- max 1 ($cpu | float64 | int) -}}
{{- end -}}
{{- end -}}

{{- define "llm-tutorial.openbaoEnabled" -}}
{{- if and .Values.runway.openbao.secretEngine .Values.runway.openbao.secretName -}}true{{- end -}}
{{- end -}}

{{/*
OpenBao 주입 어노테이션.

경로는 `<engine>/data/<name>` 입니다 — `/data/`는 KV-v2의 규약이고 차트가 붙입니다.
사용자가 직접 쓰게 두면 선언 경로와 템플릿이 읽는 경로가 어긋나는 실수가 잦습니다.

role은 항상 `default`입니다. 2.3에는 워크로드별 OpenBao role이 없습니다.
namespace는 릴리스 네임스페이스인데, 프로젝트의 OpenBao 네임스페이스 이름이 프로젝트
이름과 같으므로 이대로 맞습니다.

템플릿이 KV-v2의 `data.data` 맵을 `KEY=VALUE` 한 줄씩으로 펼칩니다. 앱의 config.py가
읽는 형식이 바로 이것입니다.
*/}}
{{- define "llm-tutorial.openbaoAnnotations" -}}
{{- $engine := .Values.runway.openbao.secretEngine -}}
{{- $name := .Values.runway.openbao.secretName -}}
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/role: "default"
vault.hashicorp.com/namespace: {{ .Release.Namespace | quote }}
vault.hashicorp.com/agent-inject-secret-{{ $name }}.env: {{ printf "%s/data/%s" $engine $name | quote }}
vault.hashicorp.com/agent-inject-template-{{ $name }}.env: |
  {{ printf "{{- with secret \"%s/data/%s\" -}}" $engine $name }}
  {{ `{{- range $k, $v := .Data.data }}` }}
  {{ `{{ $k }}={{ $v }}` }}
  {{ `{{- end }}` }}
  {{ `{{- end }}` }}
{{- end -}}
