"""LiteLLM 게이트웨이 클라이언트 — OpenAI 호환 `/chat/completions` 스트리밍.

Runway의 LLM 게이트웨이는 OpenAI 호환입니다. 그래서 특별한 SDK가 필요 없고, httpx로
직접 부르는 편이 튜토리얼에 더 맞습니다 — 오가는 것이 그대로 보입니다.

읽을 지점 두 곳:

* `stream_chat`이 돌려주는 것은 문자열이 아니라 **이벤트**입니다. 토큰이 흐르는 도중에
  모델이 "툴을 부르겠다"고 말할 수 있기 때문입니다. 에이전트(agent.py)가 그 이벤트를
  보고 다음 행동을 정합니다.
* `ToolsUnsupported` — 게이트웨이나 모델이 `tools` 필드를 아예 거부하는 경우가 있습니다.
  이것을 일반 오류와 구분해서 올리는 이유는, 에이전트가 이 하나에 대해서만 다른 전략으로
  갈아탈 수 있어야 하기 때문입니다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from .config import Settings

logger = logging.getLogger("llmchat.llm")


class UpstreamError(RuntimeError):
    """게이트웨이가 오류를 돌려줬을 때. 사용자에게 그대로 보여 줄 만한 메시지를 담습니다."""


class ToolsUnsupported(UpstreamError):
    """`tools` 필드 때문에 거부당했을 때."""


@dataclass
class ToolCall:
    id: str
    name: str = ""
    arguments: str = ""          # JSON 문자열. 스트리밍이라 조각으로 옵니다.

    def parsed_arguments(self) -> dict[str, Any]:
        try:
            value = json.loads(self.arguments or "{}")
        except json.JSONDecodeError:
            logger.warning("tool %s: 인자가 JSON이 아닙니다: %r", self.name, self.arguments)
            return {}
        return value if isinstance(value, dict) else {}


@dataclass
class Chunk:
    """스트림 한 조각. 셋 중 하나만 채워집니다."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = ""


# 게이트웨이에는 채팅 모델과 임베딩 모델이 섞여 있고, 목록 응답에는 종류 정보가
# 없습니다. 이름으로 거르는 것이 정확한 방법은 아니지만, 실제로 쓰이는 임베딩 모델
# 이름은 이 조각들 중 하나를 거의 항상 포함합니다.
EMBEDDING_NAME_HINTS = ("embed", "bge", "e5", "gte", "rerank", "minilm")


class LiteLLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # 설정에서 온 이름. 비어 있으면 `resolve_model()`이 채웁니다.
        self.model = settings.llm_model
        # "configured" | "auto" | ""  — 상태 화면이 이걸 그대로 보여 줍니다.
        self.model_source = "configured" if settings.llm_model else ""
        verify: bool | str = settings.ca_bundle or True
        self._client = httpx.AsyncClient(
            base_url=settings.llm_base_url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=httpx.Timeout(
                connect=settings.llm_connect_timeout,
                read=settings.llm_read_timeout,
                write=30.0,
                pool=30.0,
            ),
            # httpx는 REQUESTS_CA_BUNDLE 같은 환경변수를 읽지 않습니다. 번들이 필요하면
            # 코드에서 직접 넘겨야 하고, 이 한 줄이 그 자리입니다.
            verify=verify,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_models(self) -> list[str]:
        """게이트웨이가 publish한 모델 이름 목록.

        `LLM_MODEL`은 추측할 수 없는 값입니다 — 관리자가 litellm-config ConfigMap에 손으로
        적어 넣은 문자열이기 때문입니다. 그래서 앱이 스스로 물어볼 수 있게 열어 둡니다.
        """
        response = await self._client.get("/models")
        response.raise_for_status()
        data = response.json().get("data", [])
        return [entry.get("id", "") for entry in data if entry.get("id")]

    async def resolve_model(self) -> str:
        """쓸 모델을 정합니다. 설정에 있으면 그것, 없으면 게이트웨이에 물어봅니다.

        모델 이름은 관리자가 게이트웨이 설정에 손으로 적어 넣은 문자열이라 규칙이
        없고 추측할 수 없습니다. 그걸 사용자에게 알아내라고 요구하는 것이 첫 실패의
        가장 흔한 원인이었습니다.

        **무엇을 골랐는지는 반드시 밝힙니다.** 조용히 고르면 나중에 "왜 이 모델이
        답하지?"가 되고, 그때는 원인을 찾을 실마리가 없습니다.
        """
        if self.model:
            return self.model

        names = await self.list_models()
        chat_models = [n for n in names if not any(h in n.lower() for h in EMBEDDING_NAME_HINTS)]
        if not chat_models:
            raise UpstreamError(
                "게이트웨이에 쓸 수 있는 채팅 모델이 없습니다."
                + (f" 목록에 있는 것: {', '.join(names)}" if names else " 모델 목록이 비어 있습니다.")
            )

        self.model = chat_models[0]
        self.model_source = "auto"
        logger.info(
            "모델을 자동으로 골랐습니다: %s (게이트웨이가 publish한 %d개 중). "
            "다른 것을 쓰려면 LLM_MODEL을 설정하세요 — 후보: %s",
            self.model, len(names), ", ".join(chat_models),
        )
        return self.model

    def _body(self, messages: list[dict], tools: list[dict] | None) -> dict:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self._settings.llm_temperature,
            "stream": True,
        }
        if self._settings.llm_max_tokens > 0:
            body["max_tokens"] = self._settings.llm_max_tokens
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        return body

    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[Chunk]:
        body = self._body(messages, tools)
        try:
            async with self._client.stream("POST", "/chat/completions", json=body) as response:
                if response.status_code >= 400:
                    raw = (await response.aread()).decode("utf-8", "replace")
                    raise self._classify(response.status_code, raw, sent_tools=bool(tools))

                pending: dict[int, ToolCall] = {}
                async for line in response.aiter_lines():
                    chunk = _parse_sse_line(line, pending)
                    if chunk is None:
                        continue
                    if chunk is _DONE:
                        break
                    yield chunk

                if pending:
                    # 툴 콜은 조각으로 오다가 스트림이 끝날 때 완성됩니다.
                    yield Chunk(tool_calls=[pending[i] for i in sorted(pending)])

        except httpx.ConnectError as exc:
            raise UpstreamError(
                f"LLM 게이트웨이에 연결하지 못했습니다: {self._settings.llm_base_url}\n"
                f"  ({exc})\n"
                "  인클러스터 주소는 프로젝트 네임스페이스 안에서만 풀립니다. 로컬에서 실행 중이라면 "
                "https://llm.<도메인>/v1 을 쓰세요."
            ) from exc
        except httpx.ReadTimeout as exc:
            raise UpstreamError("모델이 제한 시간 안에 응답하지 않았습니다.") from exc

    @staticmethod
    def _classify(status: int, raw: str, *, sent_tools: bool) -> UpstreamError:
        detail = raw.strip()[:600]
        lowered = detail.lower()

        if sent_tools and status in (400, 404, 422, 500) and (
            "tool" in lowered or "function" in lowered
        ):
            return ToolsUnsupported(detail)

        if status == 401:
            return UpstreamError(
                "게이트웨이가 키를 거부했습니다 (401). LLM API 키가 맞는지, 삭제되지 않았는지 확인하세요."
            )
        if status == 404 and "model" in lowered:
            return UpstreamError(
                f"게이트웨이에 그 모델이 없습니다 (404). `GET {'{base}'}/models`로 실제 이름을 확인하세요.\n{detail}"
            )
        return UpstreamError(f"게이트웨이 오류 {status}: {detail}")


class _Done:
    pass


_DONE = _Done()


def _parse_sse_line(line: str, pending: dict[int, ToolCall]) -> Chunk | _Done | None:
    """SSE 한 줄 → Chunk. 관심 없는 줄이면 None.

    `pending`은 호출자가 들고 있는 툴 콜 누적 버퍼입니다. OpenAI 호환 스트림은 툴 이름과
    인자를 여러 조각으로 나눠 보내면서 `index`로만 묶어 주기 때문에, 이 상태가 필요합니다.
    """
    if not line or not line.startswith("data:"):
        return None

    payload = line[len("data:"):].strip()
    if payload == "[DONE]":
        return _DONE

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        logger.debug("JSON이 아닌 SSE 줄을 건너뜁니다: %r", payload[:120])
        return None

    choices = event.get("choices") or []
    if not choices:
        return None
    choice = choices[0]
    delta = choice.get("delta") or {}

    for call in delta.get("tool_calls") or []:
        index = call.get("index", 0)
        slot = pending.setdefault(index, ToolCall(id=call.get("id") or f"call_{index}"))
        if call.get("id"):
            slot.id = call["id"]
        function = call.get("function") or {}
        if function.get("name"):
            slot.name += function["name"]
        if function.get("arguments"):
            slot.arguments += function["arguments"]

    text = delta.get("content") or ""
    finish = choice.get("finish_reason") or ""
    if text or finish:
        return Chunk(text=text, finish_reason=finish)
    return None
