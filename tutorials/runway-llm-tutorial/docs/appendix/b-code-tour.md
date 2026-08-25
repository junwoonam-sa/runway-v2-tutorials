# 부록 B. 코드 살펴보기

챗봇 안이 어떻게 돌아가는지 궁금하다면.

**따라하는 데 필요한 내용은 아닙니다.** 본 흐름을 끝냈고 더 알고 싶을 때 보세요.

---

## 한눈에

```
app/
  chatbot/
    config.py       설정 읽기 — OpenBao에서 온 파일도 여기서 읽습니다
    llm_client.py   AI 게이트웨이와 대화 (스트리밍)
    agent.py        도구를 쓸지 판단하는 루프
    mcp_client.py   도구 서버에 붙는 쪽
    status.py       상태 화면이 보여 주는 점검
    main.py         웹 서버
  mcp_server/
    server.py       도구 서버 — 문서 색인과 검색
  frontend/         화면 (빌드 단계 없음)
```

배포되는 것은 **애플리케이션 하나**입니다. 도구 서버는 웹 서버가 자기 안에서
자식 프로세스로 띄웁니다 — 포트를 열지 않고 표준입출력으로만 이야기합니다.

---

## 읽어 볼 만한 네 곳

### 1. 키가 어떻게 들어오나 — `chatbot/config.py`

값을 세 곳에서 읽고, 뒤가 이깁니다.

```
1. .env                    로컬에서 개발할 때
2. /vault/secrets/*.env    OpenBao가 넣어 준 파일   ← 0단계에서 만든 것
3. 실제 환경변수           차트가 넣어 준 값
```

2번이 1-3에서 눈으로 확인한 그 파일입니다.

**필수값이 없어도 앱은 죽지 않습니다.** 대신 무엇이 빠졌는지 화면에서 말합니다 —
죽은 파드는 아무것도 알려 주지 못하기 때문입니다. 빠진 값을 그럴듯한 기본값으로
채우는 것이 아니라, 실패가 **보이는 곳**으로 옮긴 것입니다.

### 2. 도구를 쓸지 판단하는 곳 — `chatbot/agent.py`

```
1. AI에게 메시지 + 쓸 수 있는 도구 목록을 보낸다
2. AI가 글을 쓰면 그대로 사용자에게 전달
3. AI가 "이 도구를 부르겠다"고 하면 → 실행 → 결과를 대화에 붙이고 1번으로
4. 도구를 더 안 부르면 끝
```

4-3에서 본 `도구 호출` 줄이 3번에서 나옵니다.

쓰기 도구를 AI에게 보여 주지 않는 것도 여기입니다.

```python
LLM_VISIBLE_TOOLS = {"search_documents", "list_documents", "collection_info"}
```

목록에서 빼는 것과 **불러도 실행하지 않는 것**은 다른 방어입니다. AI는 목록에
없는 이름도 지어낼 수 있습니다.

### 3. 도구가 정의된 곳 — `mcp_server/server.py`

```python
@server.tool()
async def search_documents(query: str, top_k: int = 5) -> str:
    """이 워크스페이스에 올려 둔 문서에서 관련 대목을 찾습니다.

    사내 절차·규정·용어·설정값처럼 저장된 자료에 답이 있을 법한 질문이면 부르세요.
    일반 상식, 계산, 잡담에는 부르지 마세요.
    """
```

**이 설명문이 그대로 AI에게 전달됩니다.** AI가 도구를 안 부르거나 엉뚱한 때 부른다면,
고칠 곳은 대개 코드가 아니라 이 문장입니다. "언제 부르는지"와 "언제 부르지 않는지"를
같이 쓰는 것이 요령입니다.

### 4. 문서를 쪼개는 곳 — `chatbot/ingest.py`

제목을 만나면 거기서 끊고, 조각끼리 조금씩 겹칩니다. 겹치지 않으면 경계에 걸친
답이 어느 쪽에서도 온전히 안 나옵니다.

---

## 더 깊이

원래 개발자용으로 쓴 문서가 여섯 편 더 있습니다. 코드를 한 줄씩 짚어 가며,
왜 그렇게 만들었는지까지 설명합니다.

| | |
|---|---|
| [시작하기 전에](../deep/00-intro.md) | 개념 세 가지 |
| [환경 정보와 인증 키](../deep/01-openbao-and-keys.md) | 키 3종의 차이, OpenBao 경로 규약 |
| [스토리지와 Code Server](../deep/02-storage-and-code-server.md) | PVC, 개발 환경, 도구 준비 |
| [챗봇 앱 만들기](../deep/03-chatbot-app.md) | 설정이 실패하는 방식, 스트리밍 |
| [에이전트와 MCP](../deep/04-agent-and-mcp.md) | 툴 콜 루프, 컨테이너 안의 도구 서버 |
| [벡터 DB](../deep/05-vector-db-qdrant.md) | 임베딩, 청킹, 검색 |
| [커스텀 앱으로 배포](../deep/06-deploy-custom-app.md) | 차트를 직접 만들어 배포 |
| [개발자용 문제 해결](../deep/99-troubleshooting.md) | 로그와 명령으로 진단 |

---

## 직접 돌려 보기

클러스터 없이 노트북에서 전체를 띄울 수 있습니다. 가짜 게이트웨이와 가짜 Qdrant가
함께 뜹니다.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r app/requirements.txt
scripts/run-local.sh
```

```bash
cd app && python -m pytest
```

---

← [부록 A. 자가 빌드](a-self-build.md) | 다음: [부록 C. 문제 해결 →](c-troubleshooting.md)
