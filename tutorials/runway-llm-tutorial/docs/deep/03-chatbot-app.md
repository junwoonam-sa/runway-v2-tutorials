# Stage 2 — 챗봇 앱 만들기

> **이 단계가 끝나면**
> - FastAPI 한 프로세스가 API와 UI를 함께 서빙합니다
> - 게이트웨이의 답이 **한 글자씩 흐르는 것**을 브라우저에서 봅니다
> - 설정을 빠뜨리면 어떻게 실패하는지 직접 만들어 봤습니다

소요 50분. Code Server 안에서 진행합니다.

---

## 2-1. 구조 — 왜 이렇게 나눴나

```
app/
  chatbot/
    config.py       설정 로딩. 폴백 기본값 없음
    llm_client.py   게이트웨이 스트리밍 (httpx + SSE)
    agent.py        한 턴을 굴리는 루프 (Stage 3에서 본격적으로)
    schemas.py      요청 스키마
    main.py         FastAPI — API + 정적 파일
  frontend/         index.html / app.js / styles.css — 빌드 없음
```

**프런트와 백을 한 컨테이너에 넣었습니다.** FastAPI 한 프로세스가 `/api`와 정적
파일을 함께 서빙하면 Deployment 하나, Service 하나, HTTPRoute 하나로 끝납니다.
프런트를 따로 nginx로 띄우면 배포 단계에서 깨질 수 있는 지점이 두 배가 되는데
얻는 것이 없습니다.

**프런트엔드에 빌드 단계를 두지 않았습니다.** 정적 파일을 그대로 이미지에 넣으면
UI만 고칠 때 노드 툴체인이 필요 없습니다.

---

## 2-2. 설정 — 이 파일부터 읽으세요

[`app/chatbot/config.py`](../../app/chatbot/config.py)

값을 읽는 순서가 셋입니다. 뒤가 이깁니다.

```
1. .env                    로컬 개발 편의
2. /vault/secrets/*.env    OpenBao가 주입한 파일  ← Stage 0~1에서 만든 것
3. 실제 환경변수           차트가 넣어 준 값
```

2번이 이 튜토리얼의 핵심입니다. Code Server든 배포된 앱이든, 시크릿은 이미지에도
values.yaml에도 들어가지 않고 파일로 옵니다.

### 그럴듯한 기본값을 두지 않는 이유

`LLM_BASE_URL`에 기본값을 넣어 두면, 값을 빠뜨린 사람은 **시작 시점이 아니라 첫
메시지에서** DNS 오류나 404를 만납니다. 설정 누락이 네트워크 장애처럼 보이면 원인을
찾는 데 몇 배가 걸립니다. 그래서 이 앱은 필수값을 추측하지 않습니다.

모양을 아는 값은 모양도 검사합니다. Runway API 키(`eyJ...`)를 LLM 키 자리에 넣는
실수가 잦고, 게이트웨이가 주는 증상은 401 하나뿐이라 원인이 드러나지 않습니다.

### 그런데 예외를 던지지는 않습니다

여기가 이 앱에서 한 번 생각을 바꾼 지점입니다.

처음에는 필수값이 없으면 `ConfigError`를 올려 프로세스를 죽였습니다. 개발자에게는
맞는 동작입니다 — 터미널에 이유가 찍히고 즉시 멈춥니다.

**클러스터에서는 그게 최악입니다.** 파드가 `CrashLoopBackOff`가 되고, 이유는
`kubectl logs`에만 남습니다. 터미널을 쓰지 않는 사람에게는 화면이 아예 안 뜨는 것이
곧 "원인을 알 수 없음"입니다.

그래서 `load_settings()`는 항상 `Settings`를 돌려주고, 문제는 `problems`에 담습니다.

```python
@dataclass(frozen=True)
class Problem:
    key: str          # LLM_API_KEY
    severity: str     # fail — 채팅 불가 | warn — 일부 기능만 꺼짐
    symptom: str      # 지금 무슨 상태인지
    fix: str          # 무엇을 하면 되는지
```

**빠진 값을 채워 넣는 것이 아닙니다.** 값은 비어 있는 채로 남고 채팅도 막힙니다.
달라지는 것은 **실패가 보이는 장소**뿐입니다 — 로그에는 같은 내용이 그대로 남습니다.

터미널을 보고 있는 경로에는 엄격한 쪽을 남겨 두었습니다.

```python
load_settings()          # 웹 서버 — 뜨고 나서 화면으로 말한다
load_settings_strict()   # 개발용 진입점, MCP 서버 — 즉시 실패한다
```

### 직접 해 보기

```bash
cd ~/work/runway-llm-tutorial/app
python -c "
from chatbot.config import load_settings
for p in load_settings('/nonexistent').problems:
    print(f'[{p.key}] {p.symptom}\n  -> {p.fix}\n')
"
```

```
[LLM_BASE_URL] LLM 게이트웨이 주소가 설정되지 않았습니다.
  -> 환경변수 LLM_BASE_URL을 넣으세요. 같은 프로젝트 안에서는 http://litellm...:4000/v1 입니다.

[LLM_API_KEY] LLM API 키가 없습니다. 게이트웨이에 요청을 보낼 수 없습니다.
  -> Runway 콘솔 → 계정 설정 → 액세스 키(Access keys) → LLM API 키(LLM API Keys) → 생성. …
```

**빠진 것을 전부, 이름으로, 고칠 방법과 함께 말합니다.** 그리고 그 `fix` 문장이
그대로 `/api/status`를 거쳐 사용자 화면에 뜹니다 — 같은 문장을 두 벌 쓰지 않습니다.

### 모델 이름은 필수가 아닙니다

`LLM_MODEL`을 비워 두면 기동할 때 게이트웨이에 물어보고 채팅 모델을 하나 고릅니다
(`llm_client.resolve_model`). 이름에 `embed`·`bge`·`e5` 같은 조각이 있으면 임베딩
모델로 보고 건너뜁니다.

모델 이름은 관리자가 게이트웨이 설정에 손으로 적어 넣은 문자열이라 규칙이 없고
추측할 수 없습니다. 그걸 알아내라고 요구하는 것이 첫 실패의 가장 흔한 원인이었습니다.

**무엇을 골랐는지는 로그와 상태 화면에 명시합니다.** 조용히 고르면 나중에 "왜 이
모델이 답하지?"가 되고, 그때는 실마리가 없습니다.

---

## 2-3. 게이트웨이 클라이언트 — 스트리밍

[`app/chatbot/llm_client.py`](../../app/chatbot/llm_client.py)

게이트웨이는 OpenAI 호환입니다. 그래서 특별한 SDK가 필요 없고, httpx로 직접 부르는
편이 튜토리얼에 더 맞습니다 — 오가는 것이 그대로 보입니다.

### 왜 문자열이 아니라 이벤트를 돌려주나

```python
async def stream_chat(self, messages, tools=None) -> AsyncIterator[Chunk]:
```

토큰이 흐르는 도중에 모델이 "툴을 부르겠다"고 말할 수 있습니다. 그래서 이 함수가
돌려주는 것은 `Chunk`이고, 안에 `text` 또는 `tool_calls`가 들어 있습니다. Stage 3의
에이전트가 그걸 보고 다음 행동을 정합니다.

### SSE 파싱에서 걸리는 것

응답은 이런 줄이 이어져 옵니다.

```
data: {"choices":[{"delta":{"content":"안녕"}}]}
data: {"choices":[{"delta":{"content":"하세요"}}]}
data: [DONE]
```

툴 콜은 더 성가십니다. **이름과 인자가 여러 조각으로 나뉘어 오고, `index`로만
묶입니다.**

```
data: {... "tool_calls":[{"index":0,"id":"c1","function":{"name":"search_"}}]}
data: {... "tool_calls":[{"index":0,"function":{"name":"documents"}}]}
data: {... "tool_calls":[{"index":0,"function":{"arguments":"{\"query\":"}}]}
data: {... "tool_calls":[{"index":0,"function":{"arguments":"\"휴가\"}"}}]}
```

`_parse_sse_line`이 `pending` 버퍼에 index별로 누적합니다. 이 동작을 확인하는
테스트가 [`tests/test_pieces.py`](../../app/tests/test_pieces.py)의
`test_sse_tool_call_arrives_in_fragments` 입니다.

### httpx와 CA 번들

```python
verify=settings.ca_bundle or True,
```

**httpx는 `REQUESTS_CA_BUNDLE` 같은 환경변수를 읽지 않습니다.** requests는 읽지만
httpx는 certifi로 컨텍스트를 만들고 그 변수를 무시합니다. 사설 인증서 설치본에서
번들이 필요하면 코드에서 직접 넘겨야 하고, 이 한 줄이 그 자리입니다.

---

## 2-4. 웹 서버

[`app/chatbot/main.py`](../../app/chatbot/main.py)

| 경로 | 하는 일 |
|---|---|
| `GET /healthz` | 프로브용. **외부 의존성을 건드리지 않습니다** |
| `GET /api/status` | 항목별 점검 결과 — 증상과 **고치는 법**까지 |
| `GET /api/config` | UI가 무엇을 켤지 정하는 데 필요한 것만 (키·URL 없음) |
| `GET /api/models` | 게이트웨이 모델 목록 |
| `POST /api/chat` | SSE 스트림 |
| `/` | 정적 UI |

### `/api/status` — 진단을 앱 안으로

[`app/chatbot/status.py`](../../app/chatbot/status.py)가 여섯 가지를 점검해서
`{state, title, detail, fix}` 목록으로 돌려줍니다 — 키, 게이트웨이, 모델, MCP 서버,
벡터 DB, 임베딩.

`fix`가 이 기능의 알맹이입니다. "Qdrant 연결 실패" 한 줄은 아무것도 못 하게 하지만,
"애플리케이션 목록에서 Qdrant가 Healthy인지 보세요"는 다음 행동을 정해 줍니다.

여기에는 인증을 걸지 않았습니다. **접근 비밀번호를 아직 못 받은 사람도 "무엇이
문제인지"는 볼 수 있어야** 하기 때문입니다. 응답에 키나 URL은 들어가지 않습니다.

진단 순서에도 규칙이 하나 있습니다. `mcp_server/server.py`의 `_get_store()`는
**Qdrant에 먼저 닿아 보고 그다음 임베더를 만듭니다.** 순서가 반대면 Qdrant 주소가
틀렸을 때 임베딩 오류가 먼저 터져서, 사용자가 엉뚱한 곳을 고치게 됩니다 — 실제로
그렇게 오진하는 것을 보고 고친 부분입니다.

### 프로브에 의존성을 넣지 않는 이유

```python
@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
```

게이트웨이 상태를 여기서 확인하면, 게이트웨이가 잠깐 느려질 때 쿠버네티스가
**멀쩡한 파드를 재시작시킵니다.** 프로브는 "이 프로세스가 요청을 받을 수 있는가"만
봐야 합니다.

### 정적 마운트는 마지막에

```python
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
```

루트 마운트를 위에 두면 `/api/...` 요청까지 정적 핸들러가 먹습니다. 라우트 등록
순서가 그대로 우선순위입니다.

---

## 2-5. 실행하기

### 방법 A — 실제 게이트웨이에 붙이기 (권장)

Code Server 터미널에서:

```bash
cd ~/work/runway-llm-tutorial/app
cp .env.example .env
```

`.env`를 열어 세 줄을 채웁니다. 키는 이미 주입되어 있으므로 **거기서 읽으면
됩니다** — `.env`에 다시 적을 필요가 없습니다.

```bash
LLM_BASE_URL=https://llm.<도메인>/v1
# LLM_MODEL은 비워 두면 앱이 게이트웨이에 물어봅니다. 특정 모델을 고정하고 싶을 때만 적으세요.
# LLM_API_KEY는 /vault/secrets/llmchat.env 에서 옵니다
```

```bash
. ~/work/venv/bin/activate
python -m uvicorn chatbot.main:app --host 0.0.0.0 --port 8000 --reload
```

로그 첫 줄:

```
INFO llmchat.config read injected secret /vault/secrets/llmchat.env
INFO llmchat 설정 로드 완료 — model=... vector=off mcp=on
```

`read injected secret` 줄이 **OpenBao에서 키가 왔다는 증거**입니다.

브라우저에서 확인하려면 Code Server가 이미 웹에 노출되어 있으므로, 새 터미널에서:

```bash
curl -s localhost:8000/api/config
curl -s -N -X POST localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"한 문장으로 자기소개 해줘"}]}'
```

`data: {"type":"token","text":"안"}` 같은 줄이 하나씩 흘러나오면 성공입니다.

브라우저 UI로 보고 싶다면 Code Server의 포트 포워딩 기능(`PORTS` 탭 → Forward a
Port → 8000)을 쓰거나, 로컬에서:

```bash
kubectl -n <프로젝트> port-forward deploy/code-server 8000:8000
```

### 방법 B — 게이트웨이 없이 (노트북에서)

클러스터에 붙기 전에 배선만 확인하고 싶으면 가짜 게이트웨이가 있습니다.

```bash
scripts/run-local.sh
```

`scripts/stub_gateway.py`가 OpenAI 호환 API 세 개를 흉내 냅니다. **모델이 아닙니다** —
답변은 규칙 몇 개로 만들어 냅니다. 확인하려는 것은 답변 품질이 아니라 배선입니다.

---

## 2-6. UI 훑어보기

[`app/frontend/app.js`](../../app/frontend/app.js)

```js
async function* readSSE(response) { ... }
```

`EventSource`를 쓰지 않은 이유: GET만 되고 헤더를 붙일 수 없습니다. 대화 이력을
POST로 보내야 하고 접근 비밀번호 헤더도 필요하므로, `fetch` + 수동 파싱입니다.

서버가 보내는 이벤트는 다섯 종류입니다.

| 이벤트 | UI 동작 |
|---|---|
| `token` | 말풍선에 이어 붙임 |
| `tool_call` / `tool_result` | 접히는 활동 줄로 표시 (Stage 3) |
| `mode` | 상단 뱃지 갱신 |
| `error` / `end` | 오류 표시 / 스트림 종료 |

**도구 활동을 굳이 화면에 보여 주는 이유**: 에이전트가 왜 그 답을 했는지가 보여야
튜토리얼로 의미가 있습니다. 감춰 두면 그냥 챗봇과 구별되지 않습니다.

---

## 여기까지 되면 성공

- [ ] 설정을 비운 채 띄워도 **앱이 죽지 않고** `/api/status` 가 무엇이 빠졌는지 말해 준다
- [ ] 서버 기동 로그에 `read injected secret /vault/secrets/llmchat.env` 가 있다
- [ ] `curl /api/config` 가 모델 이름을 돌려준다
- [ ] `/api/chat` 이 `token` 이벤트를 **하나씩** 흘린다 (한꺼번에 오지 않는다)
- [ ] 브라우저에서 답변이 흐르듯 나타난다

---

## 막히면

| 증상 | 원인 | 조치 |
|---|---|---|
| 화면 상단이 🔴 | 필수값 누락 | 상태 패널의 `고치는 법`을 그대로 따르세요 |
| 401 | 키가 LLM 키가 아님 | `sk-`로 시작하는지 |
| 404 + model | 모델 이름 오타 | `GET /v1/models` 로 재확인 |
| 답이 한꺼번에 도착 | 중간 프록시가 버퍼링 | 응답 헤더 `X-Accel-Buffering: no` 확인 |
| `certificate verify failed` | 사설 CA | `CA_BUNDLE` 환경변수로 경로 지정 (Stage 5의 `runway.certs`) |
| 연결 자체가 안 됨 | 인클러스터 주소를 클러스터 밖에서 씀 | `https://llm.<도메인>/v1` 로 |

---

← [02. 스토리지와 Code Server](02-storage-and-code-server.md) | 다음: [04. 에이전트와 MCP →](04-agent-and-mcp.md)
