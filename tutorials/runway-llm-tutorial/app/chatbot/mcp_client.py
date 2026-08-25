"""MCP 클라이언트 — 자식 프로세스로 띄운 MCP 서버에 붙습니다.

세 가지 일만 합니다.

1. **spawn.** `mcp_server.server`를 자식으로 띄우고 stdin/stdout으로 JSON-RPC를 주고받습니다.
2. **번역.** MCP의 툴 목록(`name`/`description`/`input_schema`)을 OpenAI의 `tools` 배열로
   바꿉니다. 두 스키마가 거의 같아서 번역이라기보다 포장 바꾸기에 가깝습니다 —
   그리고 이 짧은 함수가 "MCP 서버를 아무 LLM에나 붙일 수 있다"는 말의 실체입니다.
3. **실행.** 모델이 부른 툴을 서버에 넘기고, 결과 텍스트를 돌려받습니다.

수명주기 주의: 세션은 FastAPI `lifespan`에서 열고 닫습니다. `AsyncExitStack`을 쓰는데,
**연 태스크와 닫는 태스크가 같아야** 합니다(anyio 취소 스코프 규칙). lifespan의 시작과
종료는 같은 태스크에서 실행되므로 조건이 맞습니다. 요청 처리 중의 `call`은 다른
태스크에서 와도 괜찮습니다 — 스트림에 쓰고 응답을 기다릴 뿐입니다.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import Client, StdioServerParameters, stdio_client

logger = logging.getLogger("llmchat.mcp")


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]

    def as_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema or {"type": "object", "properties": {}},
            },
        }


class McpToolbox:
    """MCP 서버 하나에 대한 연결. 툴이 없어도 앱은 계속 동작해야 합니다."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self._command = command
        self._env = env
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None
        self.tools: list[ToolSpec] = []
        self.last_error: str = ""

    @property
    def available(self) -> bool:
        return self._client is not None and bool(self.tools)

    async def start(self) -> None:
        """실패해도 예외를 올리지 않습니다.

        MCP가 없다고 채팅까지 죽을 이유가 없습니다. 대신 `last_error`에 이유를 남기고
        `/api/config`로 UI에 그대로 보여 줍니다 — 조용히 기능이 사라지는 것이 최악입니다.
        """
        params = StdioServerParameters(command=self._command[0], args=self._command[1:], env=self._env)
        stack = AsyncExitStack()
        try:
            client = await stack.enter_async_context(Client(stdio_client(params)))
            listing = await client.list_tools()
            self.tools = [
                ToolSpec(name=t.name, description=t.description or "", schema=t.input_schema or {})
                for t in listing.tools
            ]
            self._client = client
            self._stack = stack
            logger.info("MCP 서버 기동: %d개 툴 — %s", len(self.tools), ", ".join(t.name for t in self.tools))
        except Exception as exc:                      # noqa: BLE001
            await stack.aclose()
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("MCP 서버를 띄우지 못했습니다 (채팅은 계속됩니다): %s", self.last_error)

    async def stop(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._client = None
            self.tools = []

    def openai_tools(self, allow: set[str] | None = None) -> list[dict]:
        """모델에게 보여 줄 툴만 골라 OpenAI 형식으로.

        허용 목록을 두는 이유: 이 서버에는 `index_document`·`delete_document`처럼 쓰기
        툴도 있습니다. 대화 중에 모델이 스스로 문서를 지울 이유는 없습니다.
        """
        return [t.as_openai_tool() for t in self.tools if allow is None or t.name in allow]

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        if self._client is None:
            raise RuntimeError("MCP 서버에 연결되어 있지 않습니다.")
        result = await self._client.call_tool(name, arguments)
        text = "\n".join(
            block.text for block in (result.content or []) if getattr(block, "text", None)
        )
        if getattr(result, "is_error", False):
            # 툴 오류는 예외로 올리지 않고 텍스트로 모델에게 돌려줍니다. 모델이 보고
            # 다시 시도하거나 사용자에게 설명할 수 있습니다.
            return f"[툴 오류] {text or '(내용 없음)'}"
        return text or "(빈 결과)"
