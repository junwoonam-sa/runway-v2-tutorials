"""FastAPI 앱 — API와 정적 UI를 **한 프로세스**가 함께 서빙합니다.

프런트를 nginx로 따로 띄우지 않는 이유는 단순합니다. 그러면 Deployment 둘, Service 둘,
라우팅 규칙 둘이 되고, 배포 단계에서 깨질 수 있는 지점이 두 배가 되는데 얻는 것이
없습니다. 프런트엔드에 빌드 단계를 두지 않은 것도 같은 이유입니다 — UI만 고칠 때
노드 툴체인이 필요 없습니다.

  GET  /healthz              프로브용. 의존성을 건드리지 않습니다.
  GET  /api/config           UI가 무엇을 켤지 정하는 데 필요한 것만
  GET  /api/models           게이트웨이가 publish한 모델 이름
  POST /api/chat             SSE 스트림 (에이전트 한 턴)
  GET  /api/documents        색인된 문서 목록
  POST /api/documents        파일 업로드 → MCP `index_document`
  DEL  /api/documents/{name} 색인에서 제거
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agent import Agent, sse
from .config import ConfigError, load_settings, load_settings_strict
from .ingest import safe_source_name
from .llm_client import LiteLLMClient
from .mcp_client import McpToolbox
from .schemas import ChatRequest
from .status import build_status

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("llmchat")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# 업로드 한도. 없으면 큰 파일 하나가 파드 메모리를 통째로 가져갑니다.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_SUFFIXES = {".md", ".markdown", ".txt", ".rst"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """설정에 문제가 있어도 앱은 뜹니다.

    죽은 파드는 아무것도 알려 주지 못합니다. 화면이 떠 있어야 `/api/status` 가
    무엇이 빠졌는지 말해 줄 수 있습니다. 채팅은 준비될 때까지 막힙니다 —
    빠진 값을 그럴듯한 기본값으로 채우는 것이 아닙니다.
    """
    settings = load_settings()
    logger.info(
        "설정 로드 완료 — model=%s vector=%s mcp=%s problems=%d",
        settings.llm_model or "(자동 선택)",
        "on" if settings.vector_enabled else "off",
        "on" if settings.mcp_enabled else "off",
        len(settings.problems),
    )

    # 게이트웨이 주소나 키가 없으면 클라이언트를 만들 수 없습니다. 상태 화면이
    # 그 사실을 그대로 보고합니다.
    llm = None
    if settings.llm_base_url and settings.llm_api_key:
        llm = LiteLLMClient(settings)
        try:
            await llm.resolve_model()
        except Exception as exc:                            # noqa: BLE001
            # 기동을 막지 않습니다 — 게이트웨이가 잠깐 느릴 수도 있고, 그때마다
            # 파드가 죽으면 원인을 볼 화면조차 없습니다.
            logger.warning("기동 시 모델을 정하지 못했습니다 (상태 화면에서 다시 시도합니다): %s", exc)

    toolbox = McpToolbox(settings.mcp_command, env=dict(os.environ))
    if settings.mcp_enabled:
        # MCP 세션은 여기서 열고 아래에서 닫습니다 — 같은 태스크여야 합니다.
        await toolbox.start()

    app.state.settings = settings
    app.state.llm = llm
    app.state.toolbox = toolbox
    app.state.agent = Agent(settings, llm, toolbox) if llm else None
    try:
        yield
    finally:
        await toolbox.stop()
        if llm:
            await llm.aclose()


app = FastAPI(title="Runway LLM Tutorial Chatbot", lifespan=lifespan)


# ---------------------------------------------------------------------------
# 접근 제어
#
# Runway는 애플리케이션 호스트명 앞에 Keycloak 로그인을 붙여 주지 않습니다. 플랫폼의
# 로그인 강제는 호스트별 규칙 네 개뿐이고 애플리케이션 호스트는 거기 없습니다.
# 즉 호스트명을 아는 사람은 누구나 이 앱을 씁니다 — 그리고 이 앱은 토큰을 씁니다.
#
# 공유 비밀번호는 신원이 아닙니다. 지나가던 사용을 막을 뿐, 누가 무엇을 물었는지는
# 알려 주지 않습니다. 그래도 아무것도 없는 것보다는 낫습니다.
# ---------------------------------------------------------------------------
async def require_access(x_access_password: str = Header(default="")) -> None:
    settings = app.state.settings
    if not settings.access_password:
        return
    if x_access_password != settings.access_password:
        raise HTTPException(status_code=401, detail="접근 비밀번호가 필요합니다.")


@app.get("/healthz")
async def healthz() -> dict:
    """프로브는 게이트웨이나 Qdrant를 건드리지 않습니다.

    외부 의존성을 프로브에 넣으면, 게이트웨이가 잠깐 느려질 때 쿠버네티스가 멀쩡한
    파드를 재시작시킵니다.
    """
    return {"status": "ok"}


@app.get("/api/status")
async def get_status() -> dict:
    """무엇이 준비됐고 무엇이 안 됐는지, 항목별로.

    인증을 걸지 않습니다. 접근 비밀번호를 아직 못 받은 사람도 "무엇이 문제인지"는
    볼 수 있어야 하기 때문입니다. 응답에 키나 비밀번호는 들어가지 않습니다.
    """
    status = await build_status(app.state.settings, app.state.llm, app.state.toolbox)
    return status.as_dict()


@app.get("/api/config")
async def get_config() -> dict:
    settings = app.state.settings
    toolbox: McpToolbox = app.state.toolbox
    agent: Agent | None = app.state.agent
    llm = app.state.llm
    payload = settings.public_view()
    payload["model"] = llm.model if llm else ""
    payload["modelSource"] = llm.model_source if llm else ""
    payload["toolMode"] = agent.tool_mode if agent else "none"
    payload["tools"] = [{"name": t.name, "description": t.description} for t in toolbox.tools]
    payload["mcpError"] = toolbox.last_error
    return payload


@app.get("/api/models", dependencies=[Depends(require_access)])
async def get_models() -> dict:
    if app.state.llm is None:
        raise HTTPException(status_code=503, detail="게이트웨이가 준비되지 않았습니다. 상태 화면을 보세요.")
    try:
        return {"models": await app.state.llm.list_models()}
    except Exception as exc:                                # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"게이트웨이 조회 실패: {exc}") from exc


@app.post("/api/chat", dependencies=[Depends(require_access)])
async def chat(request: ChatRequest):
    settings = app.state.settings
    agent: Agent | None = app.state.agent

    # 준비가 안 됐으면 여기서 이유를 대며 거절합니다. 빈 값으로 게이트웨이를
    # 불러서 401이나 DNS 오류로 실패하게 두면, 사용자에게는 원인이 안 보입니다.
    if agent is None or not (app.state.llm and app.state.llm.model):
        status = await build_status(settings, app.state.llm, app.state.toolbox)
        broken = [c for c in status.checks if c.state == "fail"]
        raise HTTPException(
            status_code=503,
            detail={
                "message": "아직 대화를 시작할 수 없습니다.",
                "problems": [{"title": c.title, "detail": c.detail, "fix": c.fix} for c in broken],
            },
        )

    for message in request.messages:
        if len(message.content) > settings.max_message_chars:
            raise HTTPException(
                status_code=413,
                detail=f"메시지가 {settings.max_message_chars}자를 넘습니다.",
            )

    history = [m.model_dump() for m in request.messages]

    async def stream():
        try:
            async for item in agent.run(history, request.system_prompt):
                yield sse(item)
        except Exception as exc:                            # noqa: BLE001
            logger.exception("chat turn failed")
            yield sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        yield sse({"type": "end"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        # 프록시가 스트림을 버퍼링하면 토큰이 한꺼번에 도착해 스트리밍이 무의미해집니다.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# 문서 — 전부 MCP 서버를 통해서만 만집니다.
#
# 웹 서버가 Qdrant를 직접 부르지 않는 이유: 임베딩 모델이 한 프로세스에만 로드되게 하고,
# 문서 도메인의 규칙(청킹, 재색인 시 선삭제)이 한 곳에만 있게 하려는 것입니다.
# ---------------------------------------------------------------------------
def _require_tools() -> McpToolbox:
    toolbox: McpToolbox = app.state.toolbox
    if not toolbox.available:
        raise HTTPException(
            status_code=503,
            detail=f"MCP 서버에 연결되어 있지 않습니다. {toolbox.last_error or ''}".strip(),
        )
    return toolbox


@app.get("/api/documents", dependencies=[Depends(require_access)])
async def list_documents() -> dict:
    if not app.state.settings.vector_enabled:
        return {"enabled": False, "text": "QDRANT_URL이 설정되지 않았습니다 (Stage 4에서 켭니다)."}
    toolbox = _require_tools()
    return {"enabled": True, "text": await toolbox.call("list_documents", {})}


@app.post("/api/documents", dependencies=[Depends(require_access)])
async def upload_documents(files: list[UploadFile]) -> JSONResponse:
    toolbox = _require_tools()
    results = []
    for upload in files:
        name = safe_source_name(upload.filename or "")
        if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            results.append({"source": name, "ok": False, "message": "지원하지 않는 확장자입니다."})
            continue

        raw = await upload.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            results.append({"source": name, "ok": False, "message": "파일이 5 MiB를 넘습니다."})
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            results.append({"source": name, "ok": False, "message": "UTF-8 텍스트가 아닙니다."})
            continue

        message = await toolbox.call("index_document", {"source": name, "text": text})
        results.append({"source": name, "ok": True, "message": message})

    return JSONResponse({"results": results})


@app.delete("/api/documents/{source}", dependencies=[Depends(require_access)])
async def delete_document(source: str) -> dict:
    toolbox = _require_tools()
    return {"message": await toolbox.call("delete_document", {"source": source})}


# 정적 UI는 마지막에 붙입니다 — 루트 마운트가 위의 /api 경로를 가리지 않도록.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


def run() -> None:
    """`python -m chatbot.main` 으로 띄우는 개발용 진입점."""
    import uvicorn

    # 개발용 진입점은 사람이 터미널을 보고 있는 경로라, 즉시 실패하는 편이 낫습니다.
    # 배포된 앱(uvicorn이 직접 띄우는 경로)은 뜨고 나서 화면으로 말합니다.
    try:
        load_settings_strict()
    except ConfigError as exc:
        raise SystemExit(f"\n설정에 문제가 있습니다:\n{exc}\n")
    uvicorn.run("chatbot.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))


if __name__ == "__main__":
    run()
