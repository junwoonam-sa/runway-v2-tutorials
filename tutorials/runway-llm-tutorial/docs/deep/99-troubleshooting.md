# 99. 문제 해결

증상 → 원인 → 확인 지점. 이 튜토리얼을 따라가다 실제로 밟게 되는 것만 모았습니다.

---

## 먼저 볼 세 곳

무슨 문제든 여기부터입니다.

```bash
# 1. 앱이 스스로 진단한 결과 — 대부분 여기서 끝납니다
curl -s <앱주소>/api/status | python -m json.tool

# 2. 앱 로그 — 기동 시 세 줄이 핵심
kubectl -n <프로젝트> logs deploy/llm-tutorial --tail=100

# 3. 파드가 왜 그 상태인가
kubectl -n <프로젝트> describe pod -l app.kubernetes.io/instance=llm-tutorial | tail -30
```

기동 로그에서 확인할 세 줄:

| 줄 | 없으면 |
|---|---|
| `read injected secret /vault/secrets/...` | OpenBao 주입이 안 됨 (Stage 0/1) |
| `설정 로드 완료 — model=... vector=on mcp=on` | 설정 문제 |
| `MCP 서버 기동: 5개 툴` | MCP 자식 프로세스가 못 뜸 (Stage 3) |

---

## 인증과 키

| 증상 | 원인 | 조치 |
|---|---|---|
| 게이트웨이 401 | LLM 키가 아니라 Runway API 키를 넣음 | `sk-`로 시작해야 합니다. 앱이 시작할 때 이걸 검사합니다 |
| 게이트웨이 401 (키는 맞는데) | 키가 삭제됨 | 콘솔에서 목록 확인, 필요하면 재발급 |
| 예전에 되던 API 키가 갑자기 안 됨 | 두 번째 키를 발급해 첫 번째가 회전됨 | 한도 1 + `rotate` 전략. 조용히 폐기됩니다 |
| 키를 잃어버림 | 값은 한 번만 표시됨 | 지우고 다시 만드는 수밖에 없습니다 |
| MLflow/Gitea `permission denied` | **SSO 로그인을 한 번도 안 함** | 해당 서비스에 SSO로 로그인하세요. 권한 바인딩이 로그인 시점에 만들어집니다 |

---

## OpenBao

| 증상 | 원인 | 조치 |
|---|---|---|
| 로그인이 안 됨 | Namespace 필드가 비어 있음 | **프로젝트 ID**를 넣으세요 |
| `auth/oidc/...` 404 | 프로젝트 OpenBao 네임스페이스 미생성 | 사용자가 고칠 수 없습니다. 관리자에게 프로젝트 dependency 상태 확인 요청 |
| Secrets Engines가 안 보임 | viewer 역할 | member 이상 필요 |
| `/vault/secrets` 디렉터리가 없음 | 폼의 OpenBao 두 필드 중 하나가 빔 | 엔진과 시크릿 이름 **둘 다** 채워야 주입이 켜집니다 |
| 디렉터리는 있는데 파일이 없음 | 엔진/시크릿 이름 오타 | OpenBao UI에서 경로 재확인 |
| 파드가 `FailedMount`로 안 뜸 | ServiceAccount 토큰 볼륨 없음 | Code Server/이 차트는 기본으로 켜져 있어 드묾 |

경로를 헷갈릴 때: UI의 엔진 `tutorial` + 시크릿 `llmchat` → API 경로는
`tutorial/data/llmchat`. **`/data/`는 차트가 붙입니다.**

---

## 앱이 시작하지 않음

| 증상 | 원인 | 조치 |
|---|---|---|
| 화면 상단 배지가 🔴 | 값 누락 | 상태 패널이 항목별로 `고치는 법`을 알려 줍니다 |
| `ConfigError` (터미널) | 값 누락 | `load_settings_strict` 를 쓰는 경로입니다 — 개발용 진입점과 MCP 서버 |
| `LLM_API_KEY가 'sk-'로 시작하지 않습니다` | 키 종류를 잘못 넣음 | 콘솔 → 액세스 키 → **LLM API 키** |
| `ModuleNotFoundError: chatbot` | 작업 디렉터리 문제 | `app/` 에서 실행하거나 `PYTHONPATH=app` |
| `ModuleNotFoundError: mcp` | 의존성 미설치 | `pip install -r app/requirements.txt` |

---

## 대화가 안 됨

| 증상 | 원인 | 조치 |
|---|---|---|
| 404 + model | 모델 이름 오타 | `GET <base>/models` 로 실제 이름 확인 |
| 모델 목록엔 있는데 호출이 실패 | 그 모델의 백엔드가 없음 | 관리자 문의. 기본 설치는 항목만 있고 워크로드가 없을 수 있습니다 |
| 답이 한꺼번에 도착 | 중간 프록시 버퍼링 | 응답 헤더 `X-Accel-Buffering: no` 확인 |
| `certificate verify failed` | 사설 CA 미신뢰 | `CA_BUNDLE` / `runway.certs.enabled`. httpx는 환경변수를 읽지 않습니다 |
| `invalid path: .../ca.crt` | CA 환경변수는 있는데 파일이 없음 | 앱이 시작할 때 정리하지만, 마운트가 `optional`인지 확인 |
| 연결 자체가 안 됨 | 인클러스터 주소를 클러스터 밖에서 씀 | `https://llm.<도메인>/v1` |
| 답이 중간에 끊김 | 컨텍스트 윈도 초과 | 이력을 줄이거나 `LLM_MAX_HISTORY_MESSAGES` 조정 |

---

## 도구·MCP

| 증상 | 원인 | 조치 |
|---|---|---|
| `toolMode: none` | 자식 프로세스가 못 뜸 | `/api/config` 의 `mcpError`, 로그의 `[mcp]` 줄 |
| MCP 서버가 응답 없음 | **stdout에 뭔가 출력됨** | `print()` 를 stderr 로거로. stdout은 프로토콜 전용입니다 |
| 도구를 절대 안 부름 | docstring이 모호함 | "언제 부르는지"를 구체적으로 쓰세요 — docstring이 모델이 읽는 설명서입니다 |
| 도구를 너무 자주 부름 | 제외 조건이 없음 | "일반 상식·계산·잡담에는 부르지 마세요" 같은 문장 추가 |
| `[거부] '...'은 호출할 수 없는 툴` | 쓰기 도구를 부름 | 정상 동작입니다. `LLM_VISIBLE_TOOLS` 참고 |
| 뱃지가 "검색 주입(폴백)"으로 바뀜 | 모델/게이트웨이가 `tools`를 거부 | 정상 폴백입니다. 툴 콜을 지원하는 모델로 바꾸면 돌아옵니다 |
| orphan tool message 오류 | `assistant` 메시지를 빼고 `tool` 만 보냄 | 두 메시지는 짝입니다 |
| 툴 호출이 N회를 넘어 중단 | 모델이 도구만 부르며 돎 | `maxToolRounds` 조정, 또는 docstring 개선 |

---

## 벡터 DB

| 증상 | 원인 | 조치 |
|---|---|---|
| `Qdrant에 연결하지 못했습니다` | 주소가 틀림 | `<릴리스명>.<프로젝트>.svc.cluster.local:6333`. 릴리스명 = 애플리케이션 ID |
| 클러스터 밖에서 연결 안 됨 | 인클러스터 주소 | `kubectl port-forward svc/<릴리스명> 6333:6333` |
| **벡터 차원 불일치** | 임베딩 모델을 바꿨음 | 컬렉션은 차원이 고정입니다. 지우고 재색인: `curl -X DELETE $Q/collections/<이름>` |
| 검색 결과가 없음 | 컬렉션이 비었음 | `POST $Q/collections/<이름>/points/count` `{"exact":true}` |
| 엉뚱한 결과 | 임베딩 모델이 그 언어에 약함 | 다국어 모델로 바꾸고 **컬렉션 재생성** |
| 고유명사·오류코드를 못 찾음 | 벡터 검색의 구조적 약점 | 어휘 검색(BM25) 병행이 필요합니다 |
| 옛 내용이 계속 나옴 | 재색인 전 삭제 누락 | 같은 파일명으로 다시 올리면 앱이 먼저 지웁니다 |
| 임베딩이 매번 느림 | 로컬 모델 캐시가 PVC에 없음 | `EMBEDDING_CACHE_DIR` 을 마운트된 볼륨 아래로 |
| `게이트웨이 임베딩 실패 → 로컬로` | 게이트웨이에 임베딩 모델 없음 | 정상 폴백. 로그가 어느 쪽인지 말해 줍니다 |

---

## 배포

| 증상 | 원인 | 조치 |
|---|---|---|
| 생성했는데 아무것도 없음 | **배포 버튼 미클릭** | 상세 페이지 → 배포 |
| sync 실패 + 63자 초과 | ID가 김 | 30자 안쪽 ID로 재생성 (편집 불가) |
| sync 실패 + 호스트명 정규식 | 대문자 | 소문자로. 차트가 렌더에서 먼저 막습니다 |
| 열기 버튼 없음 | 열기 링크 미입력 | 생성 폼에 URL을 직접 입력. 차트 hostnames는 읽지 않습니다 |
| 등록 `CONNECTION_FAILED` | Argo CD가 닿지 못함 | Argo CD UI에서 `Type: helm`으로 수동 등록 |
| 등록 `AUTHENTICATION_FAILED` | PAT 스코프 | `read:package` |
| 등록 `REPOSITORY_EXISTS` | 같은 URL이 이미 등록됨 | 콘솔에는 삭제 UI가 없습니다. Argo CD UI에서 |
| Gitea 조직/저장소 404 | 비로그인 또는 팀 미배정 | **SSO 재로그인** |
| 차트 업로드 `authGroup.Verify` | 빈 토큰 또는 `write:package` 없음 | 변수가 비었는지, 스코프가 맞는지 |
| `index.yaml`에 차트가 없음 | 업로드가 실패했거나 owner가 다름 | 업로드 응답 코드부터 확인 |
| `ImagePullBackOff` + 401 | 이미지가 개인 계정에 있음 | **프로젝트 조직 네임스페이스**로 push |
| `ImagePullBackOff` (미러) | 외부 이미지가 내부 레지스트리에 없음 | 플랫폼 담당자에게 미러 경로 요청 |
| 코드 고쳤는데 반영 안 됨 | **같은 태그 재사용** | 태그를 올리세요. 이벤트에는 성공처럼 찍힙니다 |
| `FailedMount: secret not found` | 없는 CA Secret 마운트 | `runway.certs.enabled=false`, 또는 `kubectl get secret platform-root-ca` |
| `exceeded quota: requests.cpu` | 프로젝트 자원 부족 | `kubectl -n <프로젝트> describe resourcequota` |
| 빌드 job이 큐에서 안 움직임 | Gitea Actions 러너 이미지 미러 없음 | 다른 빌드 환경(로컬 도커) |

---

## 성능

| 증상 | 원인 | 조치 |
|---|---|---|
| 계산이 이상하게 느림 | 스레드 풀이 호스트 코어 수로 잡힘 | `OMP_NUM_THREADS` 등을 CPU 리밋에 맞추세요. 차트가 자동으로 합니다 |
| 첫 요청만 아주 느림 | 로컬 임베딩 모델 로딩 | 정상입니다. 캐시가 PVC에 있으면 재시작 후에는 빠릅니다 |
| 파드가 계속 재시작 | 프로브가 외부 의존성을 봄 | 이 앱의 `/healthz`는 아무것도 건드리지 않습니다 |
| 큰 이미지가 시작에 실패 | 첫 pull이 타임아웃 | startup probe의 `failureThreshold` 를 올리세요 |

---

## 무엇을 어디서 보나

| 보고 싶은 것 | 명령 |
|---|---|
| 앱이 읽은 설정 | `curl <앱>/api/config` |
| 앱 로그 | `kubectl -n <프로젝트> logs deploy/llm-tutorial -f` |
| MCP 서버 로그 | 위와 같음 — `[mcp]` 접두사가 붙습니다 |
| 파드 이벤트 | `kubectl -n <프로젝트> describe pod -l app.kubernetes.io/instance=llm-tutorial` |
| 남은 쿼터 | `kubectl -n <프로젝트> describe resourcequota` |
| Qdrant 상태 | `curl $Q/collections/<이름>` |
| Qdrant 포인트 수 | `curl -X POST $Q/collections/<이름>/points/count -d '{"exact":true}' -H 'Content-Type: application/json'` |
| 게이트웨이 모델 | `curl -H "Authorization: Bearer sk-..." <base>/models` |
| 주입된 시크릿 | `kubectl -n <프로젝트> exec deploy/llm-tutorial -- ls /vault/secrets/` |
| 차트 렌더 결과 | `helm template t ./chart -f my-values.yaml` |

---

← [06. 커스텀 애플리케이션으로 배포](06-deploy-custom-app.md) | [처음으로](../../README.md)
