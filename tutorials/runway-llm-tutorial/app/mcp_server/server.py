"""이 앱의 MCP 서버 — 앱 컨테이너 **안에서** 자식 프로세스로 돕니다.

왜 이 형태인가:

* 포트를 열지 않습니다. 부모(웹 서버)와 표준입출력으로만 이야기합니다. 그래서 배포에
  Service도, HTTPRoute도, 인증도 하나 더 늘지 않습니다. Runway는 애플리케이션 호스트명
  앞에 로그인을 붙여 주지 않으므로, "노출을 늘리지 않는다"는 것 자체가 보안 조치입니다.
* 배포물이 하나로 유지됩니다. 이미지 하나, Deployment 하나. 부모가 죽으면 자식도 같이
  갑니다 — 관리할 수명주기가 없습니다.
* 그러면서도 **진짜 MCP**입니다. 여기 있는 툴은 Claude Desktop이든 다른 MCP 클라이언트든
  그대로 붙일 수 있습니다. 나중에 HTTP 전송으로 바꾸고 싶으면 `run()` 한 줄만 바뀝니다.

이 서버가 문서 도메인 전체를 소유합니다 — 색인도, 검색도. 임베딩 모델이 한 프로세스에만
로드되게 하려는 것이 큰 이유입니다(로컬 임베딩은 수백 MB를 씁니다).

직접 띄워 볼 수 있습니다:

    cd app && python -m mcp_server.server        # stdin에서 JSON-RPC를 기다립니다
"""

from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import MCPServer

from chatbot.config import load_settings
from chatbot.embeddings import build_embedder
from chatbot.ingest import chunk_document
from chatbot.vectorstore import QdrantStore, format_hits

# stdout은 프로토콜 전용입니다. 로그를 한 줄이라도 흘리면 JSON-RPC 스트림이 깨집니다.
# 그래서 로깅은 전부 stderr로 보냅니다 — 부모가 그대로 자기 로그에 남깁니다.
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="[mcp] %(levelname)s %(message)s")
logger = logging.getLogger("mcp_server")

server = MCPServer(name="runway-docs", version="1.0.0")

_settings = None
_store: QdrantStore | None = None
_embedder = None


def _get_settings():
    """관대한 로더를 씁니다 — 이 서버는 LLM 키가 없어도 할 일이 있습니다.

    도구들이 쓰는 것은 Qdrant와 임베딩뿐입니다. LLM 키가 없다고 이 서버가 죽으면,
    부모는 "도구 서버를 띄우지 못했습니다"라고만 보고하게 되고 **진짜 원인(키 없음)이
    가려집니다.** 실제로 그렇게 오진하는 것을 보고 고쳤습니다.
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


async def _get_store() -> QdrantStore:
    """Qdrant와 임베더를 처음 필요할 때 준비합니다.

    지연 초기화인 이유: 벡터 기능을 아직 켜지 않은 Stage 3에서도 이 서버가 떠야 하고,
    임베딩 모델 로딩이 서버 기동을 붙잡고 있으면 안 되기 때문입니다.
    """
    global _store, _embedder
    settings = _get_settings()
    if not settings.vector_enabled:
        raise RuntimeError(
            "QDRANT_URL이 설정되지 않아 문서 기능이 꺼져 있습니다. Stage 4를 진행하세요."
        )
    if _store is None:
        store = QdrantStore(settings.qdrant_url, settings.qdrant_collection)
        # 순서가 중요합니다 — 벡터 DB에 먼저 닿아 봅니다. 임베더를 먼저 만들면
        # 주소가 틀렸을 때 임베딩 오류가 먼저 터져서, 사용자가 고칠 곳을 잘못 찾습니다.
        await store.ping()
        _embedder = await build_embedder(settings)
        await store.ensure_collection(_embedder.dim)
        _store = store
    return _store


# ---------------------------------------------------------------------------
# 툴
#
# 함수의 docstring과 타입 힌트가 그대로 MCP 툴 스키마가 되고, 그 스키마가 다시 모델에게
# 전달됩니다. **docstring은 모델이 읽는 설명서입니다.** "언제 부르는지"를 적으세요 —
# 모델이 툴을 안 부르거나 엉뚱할 때 고칠 곳은 대개 코드가 아니라 이 문장입니다.
# ---------------------------------------------------------------------------


@server.tool()
async def search_documents(query: str, top_k: int = 5) -> str:
    """이 워크스페이스에 올려 둔 문서에서 관련 대목을 찾습니다.

    사내 절차·규정·용어·설정값처럼 저장된 자료에 답이 있을 법한 질문이면 부르세요.
    일반 상식, 계산, 잡담에는 부르지 마세요.

    Args:
        query: 검색어. 문장보다 고유명사·식별자·오류 문자열이 잘 듣습니다.
        top_k: 가져올 발췌 수 (1~10).
    """
    store = await _get_store()
    vector = await _embedder.embed_query(query)
    hits = await store.query(vector, max(1, min(top_k, 10)))
    logger.info("search %r → %d hits", query, len(hits))
    return format_hits(hits)


@server.tool()
async def list_documents() -> str:
    """색인된 문서의 이름과 조각 수를 나열합니다. '무슨 자료가 있어?'에 답할 때 쓰세요."""
    store = await _get_store()
    rows = await store.list_sources()
    if not rows:
        return "색인된 문서가 없습니다."
    return "\n".join(f"- {r['source']} ({r['chunks']} chunks)" for r in rows)


@server.tool()
async def index_document(source: str, text: str) -> str:
    """문서 하나를 색인합니다. 같은 이름이 이미 있으면 지우고 다시 넣습니다.

    모델에게는 노출하지 않는 툴입니다(agent.py의 허용 목록 참고) — 쓰기 동작이라
    대화 중에 모델이 스스로 부를 일이 아닙니다. 웹 서버의 업로드 경로가 호출합니다.
    """
    store = await _get_store()
    chunks = chunk_document(text, source)
    if not chunks:
        return f"'{source}'에서 색인할 내용을 찾지 못했습니다."

    # 먼저 지웁니다. 새 버전이 더 짧으면 옛 조각이 남아 검색에 계속 나오기 때문입니다.
    await store.delete_by_source(source)
    vectors = await _embedder.embed_documents([c.text for c in chunks])
    await store.upsert([c.to_point(v) for c, v in zip(chunks, vectors)])
    logger.info("indexed %s → %d chunks", source, len(chunks))
    return f"'{source}' 색인 완료: {len(chunks)} chunks"


@server.tool()
async def delete_document(source: str) -> str:
    """색인에서 문서 하나를 지웁니다."""
    store = await _get_store()
    await store.delete_by_source(source)
    return f"'{source}' 삭제 완료"


@server.tool()
async def collection_info() -> str:
    """벡터 컬렉션의 현재 상태 — 이름, 임베더, 포인트 수."""
    store = await _get_store()
    total = await store.count()
    return f"collection={store.collection} embedder={_embedder.name} dim={_embedder.dim} points={total}"


def main() -> None:
    settings = _get_settings()
    # 설정 문제는 이름을 대고 stderr에 남깁니다 — 부모가 자기 로그에 그대로 옮깁니다.
    # 그렇다고 죽지는 않습니다. 도구가 실제로 필요할 때 그 자리에서 이유를 말합니다.
    for problem in settings.problems:
        print(f"[mcp] {problem.key}: {problem.symptom}", file=sys.stderr)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
