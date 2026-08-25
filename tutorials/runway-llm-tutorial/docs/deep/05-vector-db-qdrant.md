# Stage 4 — 벡터 DB (Qdrant)

> **이 단계가 끝나면**
> - 프로젝트에 Qdrant가 돌고 있습니다
> - 문서를 올리면 청크로 나뉘어 임베딩되고 저장됩니다
> - 챗봇이 **실제로 그 문서를 근거로** 답합니다

소요 50분.

---

## 4-1. 왜 벡터 DB인가

Stage 3의 `search_documents` 도구는 아직 빈 껍데기입니다. 여기서 속을 채웁니다.

문서를 프롬프트에 통째로 넣으면 안 되는 이유는 두 가지입니다. 컨텍스트 윈도가
한정되어 있고, 관계없는 내용까지 읽느라 정확도가 떨어집니다. 그래서 **질문과 가까운
대목만 찾아 넣습니다.** 그 "가까움"을 재는 것이 벡터 검색입니다.

```
문서 ──청킹──▶ 조각들 ──임베딩──▶ 벡터들 ──▶ Qdrant에 저장
                                                      │
질문 ──────────────────────임베딩──▶ 벡터 ──유사도 검색─┘──▶ 가까운 조각 N개
```

Runway 2.3.0의 애플리케이션 템플릿에는 벡터 DB가 **Milvus와 Qdrant** 둘 있습니다.
이 튜토리얼은 **Qdrant**를 씁니다 — REST API 하나로 다 되고, 볼륨이 하나이고,
`curl`로 무슨 일이 일어났는지 바로 확인할 수 있어서 배우기에 낫습니다.

---

## 4-2. Qdrant 설치

**애플리케이션** → **생성** → 템플릿에서 **Qdrant**.

| 그룹 | 필드 | 값 |
|---|---|---|
| 기본 | 이름 / **ID** | `qdrant` |
| 일반 | Replicas | `1` |
| 일반 | 클러스터 모드 / TLS | **끔** |
| 네트워크 | **외부 접근(HTTPRoute)** | **끔** ← 아래 경고 |
| 리소스 | CPU/메모리 | 기본값 (500m / 1Gi) |
| 스토리지 | 볼륨 크기 | `1Gi` 이상 |
| 스토리지 | 삭제 시 유지 | 켬 (기본값) |

생성 후 **상세 페이지에서 배포**를 누르는 것을 잊지 마세요.

> ⚠ **외부 접근을 켜지 마세요.**
>
> Qdrant 템플릿은 **API 키를 제공하지 않습니다.** 상위 차트에 `apiKey` 필드가 있지만
> Runway 래퍼가 노출하지 않고 기본값도 꺼져 있습니다. 그리고 애플리케이션 호스트명
> 앞에는 플랫폼 로그인이 붙지 않습니다.
>
> 즉 외부 접근을 켜면 **호스트명을 아는 누구나 인증 없이 벡터 DB 전체를 읽고 쓸 수
> 있습니다.** 벡터 DB에는 색인한 문서의 내용이 페이로드로 그대로 들어 있습니다.
>
> 이 튜토리얼의 챗봇은 같은 네임스페이스 안에서 부르므로 외부 접근이 필요 없습니다.

### 주소 만들기

인클러스터 주소는 이렇게 만들어집니다.

```
http://<릴리스명>.<프로젝트 ID>.svc.cluster.local:6333
```

- `<릴리스명>`은 **애플리케이션 ID**입니다. 위에서 `qdrant`로 했다면 `qdrant`.
- `6333`은 REST, `6334`는 gRPC입니다. 이 앱은 REST를 씁니다.

적어 두세요:

```
QDRANT_URL=http://qdrant.<프로젝트 ID>.svc.cluster.local:6333
```

### 살아 있는지 확인

Code Server 터미널에서:

```bash
curl -s http://qdrant.<프로젝트 ID>.svc.cluster.local:6333/collections
```

```json
{"result":{"collections":[]},"status":"ok","time":0.00001}
```

빈 목록이 정상입니다 — 아직 아무것도 안 만들었습니다.

연결이 안 되면:

```bash
kubectl -n <프로젝트> get svc | grep qdrant
kubectl -n <프로젝트> get pod -l app.kubernetes.io/instance=qdrant
```

---

## 4-3. 임베딩 — 두 갈래

[`app/chatbot/embeddings.py`](../../app/chatbot/embeddings.py)

임베딩은 텍스트를 벡터로 바꾸는 일입니다. 이 앱에는 경로가 둘 있고, **설치본마다
게이트웨이 구성이 다르기 때문에** 둘 다 필요합니다.

| 경로 | 장점 | 조건 |
|---|---|---|
| **게이트웨이** | 추가 의존성 없음, 이미지가 가벼움 | LiteLLM에 임베딩 모델이 등록되어 있어야 함 |
| **로컬** | 게이트웨이 구성과 무관 | `sentence-transformers` 필요, 가중치 다운로드 필요 |

### 어느 쪽을 쓸지 정하기

Stage 0에서 본 모델 목록을 다시 봅니다.

```bash
curl -s -H "Authorization: Bearer $LLM_API_KEY" https://llm.<도메인>/v1/models \
  | python -c "import sys,json;[print(m['id']) for m in json.load(sys.stdin)['data']]"
```

`bge`, `embedding`, `e5` 같은 이름이 있으면 **게이트웨이 경로**입니다.

```bash
export EMBEDDING_PROVIDER=gateway
export EMBEDDING_MODEL_GATEWAY=<그 이름>
```

정말 되는지 직접 확인:

```bash
curl -s -X POST https://llm.<도메인>/v1/embeddings \
  -H "Authorization: Bearer $LLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"<그 이름>","input":["테스트"]}' | head -c 200
```

없으면 **로컬 경로**입니다.

```bash
pip install -r requirements-local-embeddings.txt   # torch가 딸려 옵니다
export EMBEDDING_PROVIDER=local
export EMBEDDING_CACHE_DIR=/data/embedding-cache   # PVC 위 — 재시작해도 남게
```

> 기본 설치의 LiteLLM에는 채팅 모델 하나만 등록되어 있고 임베딩 모델은 없을 수
> 있습니다. 관리자만 추가할 수 있으므로, 없으면 로컬로 가는 것이 빠릅니다.

`EMBEDDING_PROVIDER=auto`(기본)로 두면 게이트웨이를 먼저 재보고 안 되면 로컬로
내려갑니다. **어느 쪽을 쓰는지는 반드시 로그에 남습니다:**

```
INFO llmchat.embeddings 임베딩: 게이트웨이 gateway:bge-m3 (dim=1024)
```

검색 품질이 이상할 때 가장 먼저 확인할 것이 "지금 무엇으로 임베딩하고 있는가"인데,
조용히 폴백하면 그걸 알 수 없습니다.

### E5 접두사

로컬 기본 모델(`multilingual-e5-small`)은 문서와 질문에 **서로 다른 접두사**를 붙여
학습됐습니다.

```python
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "
```

붙이지 않아도 동작은 하지만 검색 품질이 눈에 띄게 떨어집니다. **모델을 바꾸면 이
규칙도 같이 봐야 합니다** — 다른 모델은 접두사를 요구하지 않거나 다른 것을 씁니다.

---

## 4-4. 청킹

[`app/chatbot/ingest.py`](../../app/chatbot/ingest.py)

두 가지만 신경 씁니다.

**제목을 따라갑니다.** 마크다운 heading을 만나면 거기서 청크를 끊고, 그 아래
조각들에 제목을 붙여 둡니다. "3.2절이 뭐라고 하나?" 같은 질문이 통하려면 조각이
자기 위치를 알아야 합니다.

**겹칩니다.** 청크 경계에 답이 걸치면 어느 쪽에서도 온전히 안 나옵니다.
`CHUNK_OVERLAP`(150자)만큼 겹쳐서 그 확률을 낮춥니다.

```python
CHUNK_CHARS = 900       # 답 하나가 대체로 한 조각에 들어갈 크기
CHUNK_OVERLAP = 150
```

### ID를 uuid5로 만드는 이유

```python
_NAMESPACE = uuid.UUID("6f1c1a3e-2f2b-4f8a-9f0a-1a2b3c4d5e6f")
id=str(uuid.uuid5(_NAMESPACE, f"{source}#{index}"))
```

Qdrant의 포인트 ID는 부호 없는 정수이거나 UUID여야 합니다 — 파일명 문자열은 못
씁니다. uuid5를 쓰면 **같은 문서·같은 위치가 항상 같은 ID**가 되므로, 다시 색인해도
중복이 아니라 덮어쓰기가 됩니다.

그래도 재색인 전에 먼저 지웁니다:

```python
await store.delete_by_source(source)
```

새 버전이 더 짧으면 옛 조각이 남아 검색에 계속 나오기 때문입니다. 이 한 줄이 없으면
"고쳤는데 옛 내용이 나와요"가 됩니다.

---

## 4-5. Qdrant 클라이언트

[`app/chatbot/vectorstore.py`](../../app/chatbot/vectorstore.py)

`qdrant-client` 패키지를 쓰지 않고 httpx로 직접 부릅니다. 여기 있는 요청은 전부
`curl`로 똑같이 재현할 수 있고, 그래야 무슨 일이 일어났는지 눈으로 볼 수 있습니다.

### 차원이 어긋나면 — 가장 흔한 함정

```python
if existing != dim:
    raise VectorStoreError(
        f"컬렉션 '{self.collection}'의 벡터 차원은 {existing}인데 지금 임베더는 {dim}차원입니다.\n"
        ...
        f"    curl -X DELETE <QDRANT_URL>/collections/{self.collection}"
    )
```

**벡터 차원은 컬렉션을 만들 때 고정됩니다.** 임베딩 모델을 바꾸면 차원이 달라지고
(예: `multilingual-e5-small`은 384, `bge-m3`는 1024), 기존 컬렉션에 넣으려 하면
거부됩니다.

그때 할 일은 컬렉션을 지우고 다시 색인하는 것뿐입니다. 이 앱은 그 사실과 명령을
함께 알려 줍니다 — 알려 주지 않으면 Qdrant의 원본 오류 메시지만 보고 한참 헤맵니다.

### `wait=true`

```python
params={"wait": "true"},
```

색인 직후에 검색했는데 비어 나오는 혼란을 없애려는 것입니다. 대량 색인이라면
성능을 위해 끄는 편이지만, 튜토리얼에서는 "올렸으면 바로 찾아진다"가 훨씬
중요합니다.

---

## 4-6. 연결하고 확인하기

### 앱에 Qdrant 알려 주기

```bash
cd ~/work/runway-llm-tutorial/app
```

`.env`에 추가:

```bash
QDRANT_URL=http://qdrant.<프로젝트 ID>.svc.cluster.local:6333
QDRANT_COLLECTION=tutorial-docs
EMBEDDING_PROVIDER=auto
EMBEDDING_MODEL_GATEWAY=<있으면>
```

재시작:

```bash
python -m uvicorn chatbot.main:app --host 0.0.0.0 --port 8000 --reload
```

```
INFO llmchat 설정 로드 완료 — model=... vector=on mcp=on
```

`vector=on` 이면 됩니다.

### 문서 올리기

UI 우측 상단 **문서** → **파일 올리기**. `samples/` 의 두 파일을 고릅니다.

또는 명령줄로:

```bash
curl -s -X POST localhost:8000/api/documents \
  -F "files=@../samples/runway-basics.md" \
  -F "files=@../samples/llm-gateway.md"
```

```json
{"results":[{"source":"runway-basics.md","ok":true,"message":"'runway-basics.md' 색인 완료: 5 chunks"}, ...]}
```

로그에서 처음 일어난 일이 보입니다:

```
[mcp] INFO 임베딩: 게이트웨이 gateway:bge-m3 (dim=1024)
[mcp] INFO 컬렉션 tutorial-docs 생성 (dim=1024, Cosine)
[mcp] INFO indexed runway-basics.md → 5 chunks
```

### Qdrant에 실제로 들어갔는지 직접 확인

앱을 믿지 말고 저장소에 직접 물어봅니다.

```bash
Q=http://qdrant.<프로젝트 ID>.svc.cluster.local:6333

curl -s $Q/collections/tutorial-docs | python -m json.tool | head -20
curl -s -X POST $Q/collections/tutorial-docs/points/count \
  -H 'Content-Type: application/json' -d '{"exact":true}'
```

```json
{"result":{"count":9},"status":"ok"}
```

조각 하나를 눈으로:

```bash
curl -s -X POST $Q/collections/tutorial-docs/points/scroll \
  -H 'Content-Type: application/json' \
  -d '{"limit":1,"with_payload":true,"with_vector":false}' | python -m json.tool
```

`payload`에 `text`, `source`, `heading`, `index`가 들어 있습니다. **이게 나중에
모델에게 넘어가는 내용입니다.**

### 챗봇에게 물어보기

```bash
curl -s -N -X POST localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"프로젝트 ID가 어디어디에 쓰인다고 문서에 나와?"}]}'
```

```
data: {"type": "tool_call", "name": "search_documents", "arguments": {"query": "프로젝트 ID 사용처"}}
data: {"type": "tool_result", "name": "search_documents", "preview": "[1] runway-basics.md › 프로젝트 (유사도 0.812) ..."}
data: {"type": "token", "text": "문서"}
data: {"type": "token", "text": "에"}
...
```

**이 순서가 이 튜토리얼이 만들려던 것 전부입니다** — 모델이 스스로 검색을 결정하고,
MCP 도구가 벡터 DB를 뒤지고, 그 결과를 근거로 답합니다.

UI에서는 접히는 활동 줄로 보입니다. 펼치면 어떤 검색어로 무엇을 찾았는지 나옵니다.

---

## 4-7. 검색이 시원찮을 때

| 증상 | 원인 | 조치 |
|---|---|---|
| 결과가 아예 없음 | 컬렉션이 비었음 | `points/count` 로 확인 |
| 엉뚱한 조각이 나옴 | 임베딩 모델이 그 언어에 약함 | 다국어 모델로 바꾸고 **컬렉션 재생성** |
| 고유명사·오류코드를 못 찾음 | 벡터 검색의 구조적 약점 | 정확 일치가 중요하면 BM25 같은 어휘 검색을 함께 쓰는 하이브리드가 필요합니다 |
| 답이 문서와 다름 | 조각이 잘려서 문맥이 없음 | `CHUNK_CHARS` / `CHUNK_OVERLAP` 조정 후 재색인 |
| 옛 내용이 계속 나옴 | 재색인 전 삭제 누락 | 같은 파일명으로 다시 올리세요 |

`top_k`를 무작정 올리지 마세요. 각 조각이 프롬프트 토큰을 먹고, 몇 개를 넘어가면
모델이 뒤쪽을 무시하기 시작합니다. 기본 5는 그 균형에서 나온 값입니다.

---

## 여기까지 되면 성공

- [ ] Qdrant 애플리케이션이 `Healthy` 이고 외부 접근이 꺼져 있다
- [ ] `curl $Q/collections` 가 응답한다
- [ ] 앱 로그에 `vector=on` 과 `임베딩: ...` 줄이 있다
- [ ] 문서를 올리면 `N chunks` 메시지가 온다
- [ ] `points/count` 가 0보다 크다
- [ ] 문서 내용을 물으면 `tool_call` → `tool_result` → 근거 있는 답이 나온다

---

← [04. 에이전트와 MCP](04-agent-and-mcp.md) | 다음: [06. 커스텀 애플리케이션으로 배포 →](06-deploy-custom-app.md)
