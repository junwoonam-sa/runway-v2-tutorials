#!/usr/bin/env bash
# 노트북에서 전체를 띄웁니다 — 가짜 게이트웨이 + 가짜 Qdrant + 앱.
#
# Runway에 아무것도 만들지 않고 배선을 확인하는 용도입니다. 진짜 게이트웨이에 붙이려면
# app/.env 를 채우고 `scripts/run-local.sh --real` 로 실행하세요.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python}"
REAL=0
[[ "${1:-}" == "--real" ]] && REAL=1

cleanup() { jobs -p | xargs -r kill 2>/dev/null || true; }
trap cleanup EXIT

if [[ $REAL -eq 0 ]]; then
  echo "가짜 게이트웨이 :8900 / 가짜 Qdrant :6333 를 띄웁니다"
  "$PYTHON" scripts/stub_gateway.py &
  "$PYTHON" scripts/stub_qdrant.py &
  sleep 2
  export LLM_BASE_URL="http://127.0.0.1:8900/v1"
  export LLM_MODEL="stub-chat-model"
  export LLM_API_KEY="sk-stub"
  export QDRANT_URL="http://127.0.0.1:6333"
  export EMBEDDING_PROVIDER="gateway"
  export EMBEDDING_MODEL_GATEWAY="stub-embedding-model"
  # 클러스터 밖이므로 주입 시크릿 디렉터리는 없습니다.
  export VAULT_SECRETS_DIR="/nonexistent"
else
  echo "app/.env 의 값으로 실제 게이트웨이에 붙습니다"
fi

export QDRANT_COLLECTION="${QDRANT_COLLECTION:-tutorial-docs}"
cd app
echo
echo "  → http://127.0.0.1:8000"
echo
exec "$PYTHON" -m uvicorn chatbot.main:app --host 127.0.0.1 --port 8000 --reload
