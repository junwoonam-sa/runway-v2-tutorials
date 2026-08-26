# 부록 C. 문제 해결

증상 → 원인 → 할 일.

---

## 먼저 볼 곳

**챗봇 화면의 상태 배지를 먼저 보세요.** 대부분 여기서 끝납니다.

항목마다 무엇이 잘못됐는지와 **어떻게 고치는지**가 적혀 있습니다. 화면이 아예
안 뜨는 경우에만 아래 표를 보세요.

---

## 0단계 — 인증 키와 OpenBao

| 이런 화면이 나오면 | 원인 | 할 일 |
|---|---|---|
| OpenBao 로그인이 계속 실패 | Namespace 칸이 비었음 | 프로젝트 ID를 넣으세요 |
| 로그인 후 화면이 텅 비어 있음 | 프로젝트의 OpenBao 네임스페이스가 아직 준비 안 됨 | 사용자가 고칠 수 없습니다. 관리자 문의 |
| `Secrets Engines` 메뉴가 안 보임 | 보기 전용 권한 | 프로젝트 관리자에게 권한 상향 요청 |
| 키 값을 복사 전에 창을 닫음 | 값은 한 번만 표시됨 | 지우고 새로 만드세요 |
| 생성 버튼이 회색 | 이미 키가 하나 있음 | 기존 것을 쓰거나 지우고 다시 |
| 저장했는데 값이 안 보임 | 정상입니다 | OpenBao는 저장한 값을 다시 보여 주지 않습니다 |

---

## 1단계 — 개발 환경

| 이런 화면이 나오면 | 원인 | 할 일 |
|---|---|---|
| 만들었는데 아무것도 실행 안 됨 | **배포 버튼 미클릭** | 상세 화면 → 배포 |
| 배포 실패 + 알아보기 어려운 오류 | 호스트명에 대문자 | 전부 소문자로 |
| 배포 실패 + 길이 관련 오류 | ID가 너무 김 | 짧은 ID로 다시 만드세요 (ID는 수정 불가) |
| 열기 버튼이 없음 | **애플리케이션 열기 링크**를 안 넣음 | 링크를 넣고 다시 배포 |
| `exceeded quota` | 프로젝트 자원 부족 | 안 쓰는 애플리케이션 정리, 또는 관리자에게 증설 요청 |
| PVC가 계속 `Pending` | 스토리지 클래스가 처리 못 함 | 지우고 다른 클래스로 |
| `/vault/secrets/llmchat.env` 없음 | OpenBao 칸 두 개 중 하나가 빔 | **둘 다** 채우고 다시 배포 |
| 파일은 있는데 이름이 다름 | 엔진 이름이나 시크릿 이름 오타 | 0-2에서 만든 이름과 대조 |

---

## 2단계 — 벡터 DB

| 이런 화면이 나오면 | 원인 | 할 일 |
|---|---|---|
| `curl` 이 응답 없이 멈춤 | 주소가 틀림 | Qdrant의 **ID**와 **프로젝트 ID** 확인 |
| `Could not resolve host` | 주소 철자 오류 | `.svc.cluster.local` 까지 정확히 |
| `Connection refused` | Qdrant가 아직 안 뜸 | 목록에서 `Healthy` 인지 확인 |

주소를 만들 때 자주 나는 실수:

```
❌ http://qdrant.svc.cluster.local:6333              프로젝트 ID 빠짐
❌ http://qdrant.my-project.svc.cluster.local        포트 빠짐
❌ https://...                                        https 아님
✅ http://qdrant.my-project.svc.cluster.local:6333
```

---

## 3단계 — 코드 올리기와 이미지 빌드

터미널에서 (3-1의 3단계):

| 이런 메시지가 나오면 | 원인 | 할 일 |
|---|---|---|
| `Author identity unknown` | git에 사용자 정보가 없음 | `git config --global user.email "…"` 과 `user.name "…"` |
| `src refspec main does not match any` | 커밋이 하나도 없음 (위 오류의 결과) | 위를 먼저 하고 `git add -A && git commit -m "…"` |
| `Missing or invalid credentials` + `ECONNREFUSED …vscode-git.sock` | Code Server의 로그인 창을 터미널이 쓸 수 없음 | `unset GIT_ASKPASS VSCODE_GIT_ASKPASS_NODE VSCODE_GIT_ASKPASS_MAIN VSCODE_GIT_IPC_HANDLE` 뒤 `git -c credential.helper= push -u origin main` |
| `Authentication failed` | Password 칸에 계정 비밀번호를 넣음 | 그 칸에는 **토큰**을 넣습니다 (3-1의 2단계) |
| `Permission denied` (스크립트 실행 시) | 끌어다 놓은 파일에는 실행 권한이 없음 | 앞에 `bash` 를 붙여 실행하세요 — `bash scripts/package-chart.sh` |

Actions 화면에서 (3-1의 4~5단계):

| 이런 메시지가 나오면 | 원인 | 할 일 |
|---|---|---|
| `Waiting for runner…` 에서 안 움직임 | 러너가 자기 이미지를 받지 못함 | 폐쇄망에서 미러가 설정되지 않은 경우입니다. 플랫폼 담당자에게 문의하세요 |
| `password is empty` | `REGISTRY_TOKEN` 시크릿이 없음 | 저장소 → Settings → Actions → **Secrets** |
| `server gave HTTP response to HTTPS client` | `REGISTRY_HOST` 변수가 없음 | 저장소 → Settings → Actions → **Variables** 에 `gitea.<도메인>` |
| `authGroup.Verify` | 토큰에 패키지 권한이 없음 | 토큰을 다시 만들면서 `package` 를 `Write` 로 |
| 빌드는 됐는데 배포에서 `ImagePullBackOff` (`401`) | 이미지가 개인 계정에 올라감 | `REGISTRY_OWNER` 변수에 프로젝트 ID를 넣고 태그를 올려 다시 빌드 (3-1의 5단계) |

> **사용자 Settings가 아니라 저장소 Settings 입니다.** 두 곳 모두 Actions 메뉴가
> 있어서, 엉뚱한 곳에 등록해 두고 왜 안 되는지 찾게 됩니다.

---

## 3단계 — 챗봇 배포

| 이런 화면이 나오면 | 원인 | 할 일 |
|---|---|---|
| 등록했는데 차트 목록이 비어 있음 | 주소가 틀림 | 끝에 `/` 나 `index.yaml` 을 붙이지 마세요 |
| `CONNECTION_FAILED` | 클러스터가 그 주소에 닿지 못함 | 폐쇄망일 수 있습니다 → [부록 A-3](a-self-build.md) |
| `AUTHENTICATION_FAILED` | 자격증명 문제 | 비공개 저장소면 계정/토큰이 필요합니다 |
| `REPOSITORY_EXISTS` | 이미 등록된 주소 | 등록된 것을 그대로 쓰면 됩니다 |
| 배포가 거부되며 메시지가 뜸 | 값이 잘못됨 | 메시지가 어느 값인지 말해 줍니다. 클러스터에는 아무것도 안 만들어졌습니다 |
| `ImagePullBackOff` | 이미지를 못 받아옴 | 외부 레지스트리 차단 → [부록 A-3](a-self-build.md) |
| 계속 재시작 | 포트 설정이 안 맞음 | 차트 기본값을 그대로 쓰면 발생하지 않습니다 |

---

## 챗봇 화면의 상태 항목

| 항목이 🔴 / 🟡 | 뜻 | 할 일 |
|---|---|---|
| LLM API 키 — 없습니다 | OpenBao 연결 안 됨 | 3-1의 `secretEngine`/`secretName` 확인 |
| LLM API 키 — 모양이 다릅니다 | `API 키`를 넣었음 | `LLM API 키`(`sk-`)로 다시 (0-1) |
| LLM 게이트웨이 — 연결 못 함 | 주소가 틀림 | `runway.llm.baseUrl` 확인 |
| 사용 중인 모델 — 정할 수 없음 | 게이트웨이에 채팅 모델 없음 | 플랫폼 관리자 문의 |
| 도구 서버 — 못 띄웠습니다 | 앱 내부 문제 | 메시지를 그대로 문의하세요. 대화는 계속됩니다 |
| 벡터 DB — 설정되지 않음 | `vector.url` 안 넣음 | 3-1의 YAML 확인 후 다시 배포 |
| 벡터 DB — 연결 못 함 | Qdrant 주소가 틀림 | 2-2로 돌아가 확인 |

---

## 4단계 — 사용

| 이런 화면이 나오면 | 원인 | 할 일 |
|---|---|---|
| 입력창이 회색이고 안 눌림 | 상태가 🔴 | 상태 항목의 안내를 먼저 따르세요 |
| 답이 한참 안 나옴 | 모델이 느림 | 1분 정도 기다려 보세요 |
| `지원하지 않는 확장자` | PDF·Word 등 | `.md` 나 `.txt` 로 저장해서 올리세요 |
| `UTF-8 텍스트가 아닙니다` | 인코딩 문제 | 메모장에서 UTF-8로 저장 |
| 올렸는데 `0 chunks` | 파일이 비었음 | 내용이 있는지 확인 |
| 도구를 절대 안 부름 | 문서가 필요한 질문으로 안 보임 | "문서에서" 같은 말을 붙여 보세요 |
| 엉뚱한 내용을 가져옴 | 질문이 일반적임 | 구체적인 용어로 물어보세요 |
| 예전 내용으로 답함 | 문서를 고치고 다시 안 올림 | 같은 이름으로 다시 올리세요 |
| 배지가 "검색 주입(폴백)" | 모델이 도구 기능 미지원 | 고장이 아닙니다. 그대로 동작합니다 |

---

## 자주 걸리는 세 가지

**배포 버튼.** 만드는 것과 배포하는 것은 다릅니다. 설정을 고쳤을 때도 다시 배포해야
반영됩니다.

**대문자 호스트명.** 전부 소문자여야 합니다.

**키 종류.** `sk-` 로 시작해야 합니다. `eyJ` 로 시작하면 옆 탭에서 만든 것입니다.

---

## 더 깊은 진단

로그와 명령으로 파고들어야 한다면
[개발자용 문제 해결](../deep/99-troubleshooting.md)에 정리되어 있습니다.

---

← [부록 B. 코드 살펴보기](b-code-tour.md) | [처음으로](../intro/01-what-we-build.md)
