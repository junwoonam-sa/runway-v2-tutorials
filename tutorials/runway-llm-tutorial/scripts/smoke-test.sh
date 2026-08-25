#!/usr/bin/env bash
# 앱이 떠 있는 상태에서 왕복 한 번을 확인합니다.
#   scripts/smoke-test.sh [http://127.0.0.1:8000]
set -euo pipefail
BASE="${1:-http://127.0.0.1:8000}"

echo "== /healthz"
curl -fsS "$BASE/healthz"; echo

echo; echo "== /api/config   (model / toolMode / tools)"
curl -fsS "$BASE/api/config"; echo

echo; echo "== 문서 올리기"
TMP="$(mktemp -d)"
cat > "$TMP/smoke.md" <<'MD'
# 스모크 테스트 문서

이 문서의 비밀 번호표는 41-92-7 입니다.
MD
curl -fsS -X POST "$BASE/api/documents" -F "files=@$TMP/smoke.md"; echo

echo; echo "== 채팅 (문서 내용을 물어봅니다)"
# 본문을 파일로 만들어 --data-binary 로 보냅니다. 셸이 인자를 다른 인코딩으로
# 바꿔 버리는 환경(특히 Windows의 Git Bash)에서 -d 로 한글을 보내면 서버가
# "There was an error parsing the body" 로 400을 돌려줍니다.
cat > "$TMP/body.json" <<'JSON'
{"messages":[{"role":"user","content":"문서에 있는 비밀 번호표가 뭐야?"}]}
JSON
curl -fsS -N -X POST "$BASE/api/chat" \
  -H 'Content-Type: application/json' \
  --data-binary "@$TMP/body.json"
echo
rm -rf "$TMP"
echo
echo "위 스트림에 tool_call / tool_result 이벤트와 41-92-7 이 보이면 성공입니다."
