"""가짜 LLM 게이트웨이 — Runway에 붙기 전에 노트북에서 앱을 돌려 보기 위한 것.

LiteLLM이 말하는 OpenAI 호환 API 중 이 앱이 쓰는 세 개만 흉내 냅니다.

    GET  /v1/models
    POST /v1/chat/completions      (스트리밍 + 툴 콜)
    POST /v1/embeddings            (해시 기반 결정적 벡터)

**모델이 아닙니다.** 답변은 규칙 몇 개로 만들어 냅니다. 확인하려는 것은 답변 품질이
아니라 배선입니다 — 토큰이 흐르는가, 툴 콜이 왕복하는가, SSE 프레임이 맞는가.

    python scripts/stub_gateway.py            # :8900

`--no-tools`를 주면 `tools` 필드를 400으로 거부합니다. 에이전트가 검색 주입 폴백으로
갈아타는지 확인할 때 쓰세요.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="stub LLM gateway")
app.state.allow_tools = True

MODEL_ID = "stub-chat-model"
EMBEDDING_ID = "stub-embedding-model"
EMBEDDING_DIM = 64


@app.get("/v1/models")
async def models():
    return {
        "data": [
            {"id": MODEL_ID, "object": "model"},
            {"id": EMBEDDING_ID, "object": "model"},
        ]
    }


@app.post("/v1/embeddings")
async def embeddings(request: Request):
    body = await request.json()
    inputs = body.get("input") or []
    if isinstance(inputs, str):
        inputs = [inputs]
    return {
        "object": "list",
        "model": body.get("model", EMBEDDING_ID),
        "data": [{"index": i, "embedding": _hash_vector(t)} for i, t in enumerate(inputs)],
    }


def _hash_vector(text: str) -> list[float]:
    """같은 문자열은 항상 같은 벡터. 의미는 없지만 재현성은 있습니다.

    단어 단위로 해시를 더하므로 겹치는 단어가 많은 문장끼리 코사인 유사도가 올라갑니다 —
    "검색이 그럴듯하게 동작하는 것처럼" 보이기에 딱 이 정도입니다.
    """
    vector = [0.0] * EMBEDDING_DIM
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(EMBEDDING_DIM):
            vector[i] += (digest[i % len(digest)] - 127.5) / 127.5
    norm = sum(v * v for v in vector) ** 0.5 or 1.0
    return [v / norm for v in vector]


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    tools = body.get("tools")

    if tools and not app.state.allow_tools:
        # 실제 게이트웨이가 툴을 거부할 때 내는 모양. 에이전트는 이걸 ToolsUnsupported로
        # 분류해서 폴백으로 갑니다.
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "this model does not support tool calling", "type": "invalid_request_error"}},
        )

    messages = body.get("messages", [])
    already_searched = any(m.get("role") == "tool" for m in messages)
    question = next((m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), "")

    wants_documents = any(word in question for word in ("문서", "자료", "규정", "절차", "docs"))
    if tools and wants_documents and not already_searched:
        return StreamingResponse(_tool_call_stream(question), media_type="text/event-stream")

    return StreamingResponse(_text_stream(_answer(question, messages)), media_type="text/event-stream")


def _answer(question: str, messages: list[dict]) -> str:
    excerpt = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "tool"), "")
    if not excerpt:
        excerpt = next(
            (m.get("content", "") for m in reversed(messages)
             if m.get("role") == "system" and "참고 자료" in (m.get("content") or "")),
            "",
        )
    if excerpt:
        return f"(스텁) 찾은 자료를 근거로 답합니다.\n\n{excerpt.strip()[:400]}"
    return f"(스텁) '{question.strip()[:60]}' 라고 물으셨네요. 진짜 모델이 아니라 배선 확인용 응답입니다."


def _frame(delta: dict, finish: str | None = None) -> str:
    payload = {
        "id": "chatcmpl-stub",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _text_stream(text: str):
    # 한 글자씩 보내 스트리밍 UI가 실제로 흐르는지 보이게 합니다.
    for character in text:
        yield _frame({"content": character})
    yield _frame({}, finish="stop")
    yield "data: [DONE]\n\n"


def _tool_call_stream(question: str):
    """툴 콜도 조각으로 보냅니다 — 실제 게이트웨이가 그렇게 하기 때문입니다."""
    yield _frame({"tool_calls": [{"index": 0, "id": "call_stub_1", "type": "function",
                                  "function": {"name": "search_", "arguments": ""}}]})
    yield _frame({"tool_calls": [{"index": 0, "function": {"name": "documents"}}]})
    arguments = json.dumps({"query": question[:60]}, ensure_ascii=False)
    half = len(arguments) // 2
    yield _frame({"tool_calls": [{"index": 0, "function": {"arguments": arguments[:half]}}]})
    yield _frame({"tool_calls": [{"index": 0, "function": {"arguments": arguments[half:]}}]})
    yield _frame({}, finish="tool_calls")
    yield "data: [DONE]\n\n"


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8900)
    parser.add_argument("--no-tools", action="store_true", help="tools 필드를 400으로 거부합니다")
    args = parser.parse_args()

    app.state.allow_tools = not args.no_tools
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
