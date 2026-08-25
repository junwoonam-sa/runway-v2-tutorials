"""상태 점검 — 비개발자가 실제로 겪는 네 가지 상황.

확인하려는 것은 "상태를 맞게 계산하는가"만이 아닙니다. **문제일 때 다음에 할 행동을
말해 주는가**가 이 기능의 존재 이유이므로, `fix` 문구도 함께 검사합니다.
"""

from __future__ import annotations

import pytest

from chatbot.config import Problem, Settings
from chatbot.llm_client import LiteLLMClient, UpstreamError
from chatbot.mcp_client import ToolSpec
from chatbot.status import build_status

pytestmark = pytest.mark.asyncio


def make_settings(**overrides) -> Settings:
    base = dict(
        llm_base_url="http://litellm:4000/v1",
        llm_model="",
        llm_api_key="sk-test",
    )
    base.update(overrides)
    return Settings(**base)


class FakeLLM:
    """LiteLLMClient의 자리에 끼웁니다 — 네트워크 없이 같은 인터페이스만."""

    def __init__(self, models=("chat-model", "bge-m3"), fail=False):
        self._models = list(models)
        self._fail = fail
        self.model = ""
        self.model_source = ""

    async def list_models(self):
        if self._fail:
            raise ConnectionError("connection refused")
        return self._models

    async def resolve_model(self):
        return await LiteLLMClient.resolve_model(self)      # 실제 선택 로직을 그대로 씁니다


class FakeToolbox:
    def __init__(self, tools=("collection_info",), info="collection=docs embedder=gateway:bge-m3 dim=1024 points=7"):
        self.tools = [ToolSpec(name=n, description="", schema={}) for n in tools]
        self.last_error = ""
        self._info = info

    @property
    def available(self):
        return bool(self.tools)

    async def call(self, name, arguments):
        if isinstance(self._info, Exception):
            raise self._info
        return self._info


def by_key(status):
    return {c.key: c for c in status.checks}


async def test_everything_configured_reads_as_ready():
    status = await build_status(
        make_settings(qdrant_url="http://qdrant:6333"), FakeLLM(), FakeToolbox()
    )
    assert status.overall == "ok"
    assert status.chat_ready is True
    assert status.summary == "모두 정상입니다."


async def test_missing_key_blocks_chat_and_names_the_console_path():
    settings = make_settings(
        llm_api_key="",
        problems=(Problem("LLM_API_KEY", "fail", "LLM API 키가 없습니다.",
                          "콘솔 → 액세스 키(Access keys) → LLM API 키 → 생성"),),
    )
    status = await build_status(settings, None, FakeToolbox())

    assert status.chat_ready is False
    assert status.overall == "fail"
    assert "액세스 키" in by_key(status)["key"].fix


async def test_unreachable_gateway_explains_which_address_to_use():
    status = await build_status(make_settings(), FakeLLM(fail=True), FakeToolbox())

    gateway = by_key(status)["gateway"]
    assert gateway.state == "fail"
    assert "litellm.runway-applications" in gateway.fix     # 인클러스터 주소를 알려 줘야 합니다
    assert status.chat_ready is False


async def test_model_is_picked_automatically_and_says_so():
    """비개발자가 모델 이름을 알아낼 필요가 없어야 합니다 — 다만 무엇을 골랐는지는 밝힙니다."""
    llm = FakeLLM(models=("bge-m3", "chat-model"))
    status = await build_status(make_settings(), llm, FakeToolbox())

    model = by_key(status)["model"]
    assert model.state == "ok"
    assert "chat-model" in model.detail          # 임베딩 모델(bge)은 건너뜁니다
    assert "자동" in model.detail


async def test_gateway_with_only_embedding_models_is_reported():
    llm = FakeLLM(models=("bge-m3", "text-embedding-3-small"))
    status = await build_status(make_settings(), llm, FakeToolbox())

    assert by_key(status)["model"].state == "fail"
    assert status.chat_ready is False


async def test_without_qdrant_chat_still_works_and_documents_are_marked_off():
    """벡터 DB가 없다고 대화까지 막지 않습니다. 꺼진 기능만 그렇다고 말합니다."""
    status = await build_status(make_settings(), FakeLLM(), FakeToolbox())

    assert status.chat_ready is True
    vector = by_key(status)["vector"]
    assert vector.state == "warn"
    assert "QDRANT_URL" in vector.fix
    assert "Qdrant" in vector.fix


async def test_unreachable_qdrant_points_at_the_application_list():
    settings = make_settings(qdrant_url="http://qdrant:6333")
    status = await build_status(settings, FakeLLM(), FakeToolbox(info=RuntimeError("connect failed")))

    vector = by_key(status)["vector"]
    assert vector.state == "fail"
    assert "Healthy" in vector.fix              # 콘솔에서 볼 곳을 알려 줍니다
    assert status.chat_ready is True            # 그래도 대화는 됩니다


async def test_embedding_check_says_where_it_runs():
    settings = make_settings(qdrant_url="http://qdrant:6333")

    gateway = await build_status(settings, FakeLLM(), FakeToolbox())
    assert "게이트웨이" in by_key(gateway)["embedding"].detail

    local = await build_status(
        settings, FakeLLM(),
        FakeToolbox(info="collection=docs embedder=local:intfloat/multilingual-e5-small dim=384 points=0"),
    )
    assert "앱 안에서" in by_key(local)["embedding"].detail


async def test_mcp_failure_is_reported_without_killing_chat():
    toolbox = FakeToolbox(tools=())
    toolbox.last_error = "FileNotFoundError: python"
    status = await build_status(make_settings(), FakeLLM(), toolbox)

    mcp = by_key(status)["mcp"]
    assert mcp.state == "fail"
    assert "FileNotFoundError" in mcp.detail
    assert status.chat_ready is True


async def test_empty_collection_says_so_in_plain_words():
    settings = make_settings(qdrant_url="http://qdrant:6333")
    status = await build_status(
        settings, FakeLLM(), FakeToolbox(info="collection=docs embedder=gateway:bge dim=8 points=0")
    )
    assert "아직 올린 문서가 없습니다" in by_key(status)["vector"].detail
