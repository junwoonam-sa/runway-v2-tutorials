"""청킹, SSE 파싱, MCP→OpenAI 스키마 변환, Qdrant 요청 본문."""

from __future__ import annotations

import httpx
import pytest

from chatbot.ingest import CHUNK_CHARS, chunk_document, safe_source_name
from chatbot.llm_client import ToolCall, _parse_sse_line
from chatbot.mcp_client import ToolSpec
from chatbot.vectorstore import Hit, QdrantStore, format_hits

pytestmark_asyncio = pytest.mark.asyncio


# --- 청킹 -------------------------------------------------------------------

def test_headings_start_new_chunks_and_are_remembered():
    text = "# 개요\n한 줄.\n\n## 설치\n두 줄.\n"
    chunks = chunk_document(text, "guide.md")

    assert [c.heading for c in chunks] == ["개요", "설치"]
    assert "한 줄." in chunks[0].text and "두 줄." in chunks[1].text


def test_long_sections_are_split_with_overlap():
    body = "\n".join(f"{i}번째 문장입니다. 어느 정도 길이가 있어야 나뉩니다." % () for i in range(120))
    chunks = chunk_document("# 긴 절\n" + body, "long.md")

    assert len(chunks) > 1
    assert all(len(c.text) < CHUNK_CHARS * 2 for c in chunks)
    # 경계에 걸친 답을 잃지 않도록 뒤 청크가 앞 청크의 꼬리를 물고 시작합니다.
    assert chunks[1].text[:40] in chunks[0].text


def test_chunk_ids_are_stable_across_reindexing():
    first = chunk_document("# A\n내용", "doc.md")
    second = chunk_document("# A\n내용", "doc.md")
    assert [c.id for c in first] == [c.id for c in second]
    # 다른 문서면 다른 ID.
    assert first[0].id != chunk_document("# A\n내용", "other.md")[0].id


def test_upload_filenames_are_stripped_of_path_elements():
    assert safe_source_name("../../etc/passwd") == "passwd"
    assert safe_source_name(r"C:\docs\a.md") == "a.md"
    assert safe_source_name("") == "untitled"


# --- SSE --------------------------------------------------------------------

def test_sse_text_delta():
    pending: dict[int, ToolCall] = {}
    chunk = _parse_sse_line('data: {"choices":[{"delta":{"content":"안녕"}}]}', pending)
    assert chunk.text == "안녕"


def test_sse_tool_call_arrives_in_fragments():
    """이름과 인자가 조각으로 오고 index로만 묶입니다 — 그래서 누적 버퍼가 필요합니다."""
    pending: dict[int, ToolCall] = {}
    frames = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1","function":{"name":"search_"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"documents"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"query\\":"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"휴가\\"}"}}]}}]}',
    ]
    for frame in frames:
        _parse_sse_line(frame, pending)

    call = pending[0]
    assert call.name == "search_documents"
    assert call.parsed_arguments() == {"query": "휴가"}


def test_sse_ignores_keepalives_and_broken_json():
    pending: dict[int, ToolCall] = {}
    assert _parse_sse_line("", pending) is None
    assert _parse_sse_line(": keep-alive", pending) is None
    assert _parse_sse_line("data: {not json", pending) is None


# --- MCP → OpenAI -----------------------------------------------------------

def test_mcp_tool_becomes_an_openai_function():
    spec = ToolSpec(
        name="search_documents",
        description="문서를 찾습니다.",
        schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    tool = spec.as_openai_tool()

    assert tool["type"] == "function"
    assert tool["function"]["name"] == "search_documents"
    assert tool["function"]["parameters"]["required"] == ["query"]


def test_tool_without_schema_still_produces_a_valid_object():
    tool = ToolSpec(name="list_documents", description="", schema={}).as_openai_tool()
    assert tool["function"]["parameters"] == {"type": "object", "properties": {}}


# --- Qdrant -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_collection_is_created_with_the_embedder_dimension():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(404)
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"result": True, "status": "ok"})

    store = QdrantStore("http://qdrant:6333", "docs")
    store._client = httpx.AsyncClient(base_url="http://qdrant:6333", transport=httpx.MockTransport(handler))

    assert await store.ensure_collection(384) is True
    assert '"size":384' in seen["body"].replace(" ", "") and "Cosine" in seen["body"]


@pytest.mark.asyncio
async def test_dimension_mismatch_names_the_fix():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"result": {"config": {"params": {"vectors": {"size": 1024}}}}}
        )

    store = QdrantStore("http://qdrant:6333", "docs")
    store._client = httpx.AsyncClient(base_url="http://qdrant:6333", transport=httpx.MockTransport(handler))

    with pytest.raises(Exception) as exc:
        await store.ensure_collection(384)
    message = str(exc.value)
    assert "1024" in message and "384" in message and "DELETE" in message


def test_hits_are_formatted_with_their_source():
    text = format_hits([Hit(score=0.87, text="연차는 15일", source="policy.md", heading="휴가")])
    assert "policy.md" in text and "휴가" in text and "0.87" in text
    assert format_hits([]) == "검색 결과가 없습니다."
