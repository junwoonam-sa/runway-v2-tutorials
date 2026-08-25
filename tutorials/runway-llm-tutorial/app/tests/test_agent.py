"""에이전트 — 툴 콜 루프와 폴백 전환.

게이트웨이도 MCP 서버도 띄우지 않고, 둘 다 가짜로 바꿔 끼웁니다. 확인하려는 것은
"모델이 툴을 부르면 실행하고 결과를 대화에 되먹이는가"와 "tools가 거부당하면 조용히
죽지 않고 다른 전략으로 가는가" 두 가지입니다.
"""

from __future__ import annotations

import pytest

from chatbot.agent import Agent
from chatbot.config import Settings
from chatbot.llm_client import Chunk, ToolCall, ToolsUnsupported
from chatbot.mcp_client import ToolSpec

pytestmark = pytest.mark.asyncio


def make_settings(**overrides) -> Settings:
    base = dict(
        llm_base_url="http://litellm:4000/v1",
        llm_model="demo",
        llm_api_key="sk-test",
        system_prompt="너는 튜토리얼 도우미다.",
        max_tool_rounds=2,
    )
    base.update(overrides)
    return Settings(**base)


class FakeLLM:
    """미리 정해 둔 스크립트를 순서대로 흘립니다."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def stream_chat(self, messages, tools=None):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        for chunk in step:
            yield chunk


class FakeToolbox:
    def __init__(self, tools=("search_documents",), result="문서 발췌 …"):
        self.tools = [ToolSpec(name=n, description=n, schema={"type": "object"}) for n in tools]
        self.result = result
        self.calls = []
        self.last_error = ""

    @property
    def available(self):
        return bool(self.tools)

    def openai_tools(self, allow=None):
        return [t.as_openai_tool() for t in self.tools if allow is None or t.name in allow]

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result


async def collect(agent, history):
    return [event async for event in agent.run(history)]


async def test_plain_answer_streams_tokens():
    llm = FakeLLM([[Chunk(text="안"), Chunk(text="녕"), Chunk(finish_reason="stop")]])
    agent = Agent(make_settings(), llm, FakeToolbox(tools=()))

    events = await collect(agent, [{"role": "user", "content": "안녕"}])

    assert [e["text"] for e in events if e["type"] == "token"] == ["안", "녕"]
    assert events[-1]["type"] == "done"
    # 툴이 없으면 tools 필드 자체를 보내지 않습니다.
    assert llm.calls[0]["tools"] is None
    # 시스템 프롬프트가 항상 맨 앞.
    assert llm.calls[0]["messages"][0]["role"] == "system"


async def test_tool_call_is_executed_and_fed_back():
    llm = FakeLLM(
        [
            [Chunk(tool_calls=[ToolCall(id="c1", name="search_documents", arguments='{"query":"휴가"}')])],
            [Chunk(text="문서에 따르면…"), Chunk(finish_reason="stop")],
        ]
    )
    toolbox = FakeToolbox(result="[1] policy.md › 휴가\n연차는 15일")
    agent = Agent(make_settings(), llm, toolbox)

    events = await collect(agent, [{"role": "user", "content": "휴가 며칠?"}])
    kinds = [e["type"] for e in events]

    assert "tool_call" in kinds and "tool_result" in kinds
    assert toolbox.calls == [("search_documents", {"query": "휴가"})]

    # 두 번째 요청의 대화에 assistant(tool_calls) + tool 결과가 짝으로 들어가야 합니다.
    second = llm.calls[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"]
    assert second[-1] == {"role": "tool", "tool_call_id": "c1", "content": toolbox.result}


async def test_write_tools_are_not_offered_and_are_refused_if_called():
    llm = FakeLLM(
        [
            [Chunk(tool_calls=[ToolCall(id="c1", name="delete_document", arguments='{"source":"a.md"}')])],
            [Chunk(text="지울 수 없습니다."), Chunk(finish_reason="stop")],
        ]
    )
    toolbox = FakeToolbox(tools=("search_documents", "delete_document"))
    agent = Agent(make_settings(), llm, toolbox)

    await collect(agent, [{"role": "user", "content": "a.md 지워"}])

    offered = {t["function"]["name"] for t in llm.calls[0]["tools"]}
    assert offered == {"search_documents"}          # 쓰기 툴은 애초에 안 보여 줍니다
    assert toolbox.calls == []                      # 그래도 부르면 실행하지 않습니다


async def test_tools_rejected_switches_to_retrieval_fallback():
    llm = FakeLLM(
        [
            ToolsUnsupported("this model does not support tools"),
            [Chunk(text="자료에 따르면…"), Chunk(finish_reason="stop")],
        ]
    )
    toolbox = FakeToolbox(result="[1] runbook.md\n재시작 절차")
    agent = Agent(make_settings(), llm, toolbox)

    events = await collect(agent, [{"role": "user", "content": "재시작 어떻게 해?"}])

    assert agent.tools_unsupported is True
    assert agent.tool_mode == "retrieval-fallback"
    assert {"type": "mode", "mode": "retrieval-fallback"} in events
    assert toolbox.calls == [("search_documents", {"query": "재시작 어떻게 해?"})]

    # 두 번째 시도에는 tools를 보내지 않고, 검색 결과가 참고 자료로 들어갑니다.
    assert llm.calls[1]["tools"] is None
    injected = [m for m in llm.calls[1]["messages"] if m["role"] == "system"]
    assert any("참고 자료" in m["content"] for m in injected)


async def test_tool_loop_stops_at_the_configured_ceiling():
    """모델이 계속 툴만 부르면 끊습니다 — 무한 왕복은 토큰과 시간을 그대로 태웁니다."""
    forever = [[Chunk(tool_calls=[ToolCall(id=f"c{i}", name="search_documents", arguments="{}")])] for i in range(5)]
    agent = Agent(make_settings(max_tool_rounds=2), FakeLLM(forever), FakeToolbox())

    events = await collect(agent, [{"role": "user", "content": "무한"}])

    assert events[-1]["type"] == "error"
    assert "2회" in events[-1]["message"]
