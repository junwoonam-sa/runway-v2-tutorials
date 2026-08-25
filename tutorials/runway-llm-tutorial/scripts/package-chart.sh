#!/usr/bin/env bash
# 차트를 패키징해 Gitea Helm 레지스트리에 올립니다.
#
#   GITEA_HOST=gitea.<도메인> GITEA_USER=<계정> GITEA_OWNER=<계정 또는 조직> \
#   scripts/package-chart.sh
#
# PAT은 프롬프트로 받습니다 — URL에 넣으면 셸 히스토리와 .git/config에 남고,
# code-server의 홈은 영속 볼륨이라 재시작해도 남습니다.
#
# 차트 업로드에 필요한 스코프는 write:package 입니다. write:repository 로는 안 됩니다.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${GITEA_HOST:?GITEA_HOST를 설정하세요 (예: gitea.example.com)}"
: "${GITEA_USER:?GITEA_USER를 설정하세요}"
: "${GITEA_OWNER:?GITEA_OWNER를 설정하세요 (개인 계정 또는 조직)}"

NAME=$(awk '/^name:/{print $2}' chart/Chart.yaml)
VERSION=$(awk '/^version:/{print $2}' chart/Chart.yaml)
echo "차트 ${NAME}-${VERSION}"

read -rsp "Gitea PAT: " GITEA_PAT; echo

if command -v helm >/dev/null; then
  helm package ./chart >/dev/null
else
  # helm이 없어도 됩니다. 규칙은 두 가지 — 아카이브 루트 디렉터리 이름이 Chart.yaml의
  # name 과 같을 것, 파일명이 <name>-<version>.tgz 일 것.
  echo "helm이 없어 직접 묶습니다"
  rm -rf /tmp/pkg && mkdir -p "/tmp/pkg/${NAME}"
  cp -r ./chart/* "/tmp/pkg/${NAME}/"
  tar -czf "${NAME}-${VERSION}.tgz" -C /tmp/pkg "${NAME}"
fi

echo "업로드…"
curl -i --user "${GITEA_USER}:${GITEA_PAT}" \
  -X POST --upload-file "${NAME}-${VERSION}.tgz" \
  "https://${GITEA_HOST}/api/packages/${GITEA_OWNER}/helm/api/charts"

echo
echo "확인 — entries: 아래에 ${NAME} 과 ${VERSION} 이 보이면 리포지토리로서 완전합니다."
curl -fsS --user "${GITEA_USER}:${GITEA_PAT}" \
  "https://${GITEA_HOST}/api/packages/${GITEA_OWNER}/helm/index.yaml" | head -30

echo
echo "애플리케이션 생성 폼에 넣을 리포지토리 URL:"
echo "  https://${GITEA_HOST}/api/packages/${GITEA_OWNER}/helm"
echo "  (브라우저로 열면 404가 나는 것이 정상입니다 — Helm 리포지토리는 베이스 경로에"
echo "   페이지를 서빙하지 않습니다. <url>/index.yaml 만 있으면 됩니다.)"
