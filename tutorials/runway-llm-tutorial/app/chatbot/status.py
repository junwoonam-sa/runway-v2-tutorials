"""앱이 스스로를 점검해서 **사람이 읽는 말로** 답합니다.

이 파일이 있는 이유는 하나입니다 — 터미널을 쓰지 않는 사람도 무엇이 잘못됐는지
알 수 있어야 하기 때문입니다.

로그와 `kubectl describe`에 답이 있다는 것은 그걸 볼 줄 아는 사람에게만 참입니다.
그래서 점검을 앱 안으로 가져와, 첫 화면에서 항목별로 보여 줍니다.

각 항목은 세 가지를 말합니다:

    지금 어떤 상태인가   (state: ok | warn | fail)
    무엇이 보이는가      (detail — 증상, 값, 개수)
    무엇을 하면 되는가   (fix — 문제일 때만)

`fix`가 이 파일의 알맹이입니다. "Qdrant 연결 실패" 한 줄은 아무것도 못 하게 하지만,
"애플리케이션 목록에서 Qdrant가 Healthy인지 보세요"는 다음 행동을 정해 줍니다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .config import Settings
from .llm_client import LiteLLMClient
from .mcp_client import McpToolbox

logger = logging.getLogger("llmchat.status")

OK, WARN, FAIL = "ok", "warn", "fail"

# collection_info 도구가 돌려주는 한 줄에서 값을 뽑습니다.
#   collection=tutorial-docs embedder=gateway:bge-m3 dim=1024 points=42
_INFO = re.compile(r"(\w+)=(\S+)")


# 도구 오류 원문 앞에 붙는 기계적인 머리말. 사람에게는 소음입니다.
_NOISE = re.compile(r"^\[툴 오류\]\s*(Error executing tool \w+:)?\s*")


def _one_line(text: str, limit: int = 180) -> str:
    flat = " ".join(_NOISE.sub("", text).split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


@dataclass
class Check:
    key: str
    title: str
    state: str
    detail: str
    fix: str = ""

    def as_dict(self) -> dict:
        return {"key": self.key, "title": self.title, "state": self.state,
                "detail": self.detail, "fix": self.fix}


@dataclass
class Status:
    checks: list[Check] = field(default_factory=list)

    @property
    def overall(self) -> str:
        states = {c.state for c in self.checks}
        return FAIL if FAIL in states else (WARN if WARN in states else OK)

    @property
    def chat_ready(self) -> bool:
        """채팅을 시작할 수 있는가. 문서 기능은 없어도 대화는 됩니다."""
        blocking = {"key", "gateway", "model"}
        return not any(c.state == FAIL for c in self.checks if c.key in blocking)

    def as_dict(self) -> dict:
        return {
            "overall": self.overall,
            "chatReady": self.chat_ready,
            "summary": self.summary,
            "checks": [c.as_dict() for c in self.checks],
        }

    @property
    def summary(self) -> str:
        """가장 먼저 손봐야 할 것 한 줄. 입력창이 막혔을 때 그 아래에 이 문장이 뜹니다."""
        for state in (FAIL, WARN):
            first = next((c for c in self.checks if c.state == state), None)
            if first:
                # 항목 이름이 증상 문장 안에 이미 들어 있으면 앞에 또 붙이지 않습니다
                # ("LLM API 키 — LLM API 키가 없습니다" 같은 반복을 막습니다).
                if first.detail.startswith(first.title):
                    return first.detail
                return f"{first.title} — {first.detail}"
        return "모두 정상입니다."


async def build_status(settings: Settings, llm: LiteLLMClient | None, toolbox: McpToolbox) -> Status:
    status = Status()
    problems = {p.key: p for p in settings.problems}

    status.checks.append(_check_key(problems))
    gateway = await _check_gateway(settings, llm, problems)
    status.checks.append(gateway)
    status.checks.append(await _check_model(llm, gateway))
    status.checks.append(_check_mcp(settings, toolbox))

    vector, embedding = await _check_documents(settings, toolbox)
    status.checks.append(vector)
    status.checks.append(embedding)
    return status


def _check_key(problems: dict) -> Check:
    problem = problems.get("LLM_API_KEY")
    if problem:
        return Check("key", "LLM API 키", FAIL, problem.symptom, problem.fix)
    return Check("key", "LLM API 키", OK, "키가 주입되어 있습니다.")


async def _check_gateway(settings: Settings, llm: LiteLLMClient | None, problems: dict) -> Check:
    problem = problems.get("LLM_BASE_URL")
    if problem:
        return Check("gateway", "LLM 게이트웨이", FAIL, problem.symptom, problem.fix)
    if llm is None:
        return Check("gateway", "LLM 게이트웨이", FAIL,
                     "키가 없어 게이트웨이에 연결하지 않았습니다.",
                     "위의 LLM API 키 항목을 먼저 해결하세요.")

    try:
        models = await llm.list_models()
    except Exception as exc:                                # noqa: BLE001
        return Check(
            "gateway", "LLM 게이트웨이", FAIL,
            f"연결하지 못했습니다: {type(exc).__name__}",
            f"주소가 {settings.llm_base_url} 로 되어 있습니다. 프로젝트 안에서 접속할 때는 "
            "http://litellm.runway-applications.svc.cluster.local:4000/v1, "
            "바깥에서는 https://llm.<도메인>/v1 입니다. 401이 나오면 키 문제입니다.",
        )

    if not models:
        return Check("gateway", "LLM 게이트웨이", WARN,
                     "연결은 되는데 모델 목록이 비어 있습니다.",
                     "게이트웨이에 등록된 모델이 없습니다. 플랫폼 관리자에게 문의하세요.")
    return Check("gateway", "LLM 게이트웨이", OK, f"연결됨. 모델 {len(models)}개가 있습니다.")


async def _check_model(llm: LiteLLMClient | None, gateway: Check) -> Check:
    if llm is None or gateway.state == FAIL:
        return Check("model", "사용 중인 모델", FAIL, "게이트웨이에 연결되지 않아 정할 수 없습니다.",
                     "위의 게이트웨이 항목을 먼저 해결하세요.")
    try:
        model = await llm.resolve_model()
    except Exception as exc:                                # noqa: BLE001
        return Check("model", "사용 중인 모델", FAIL, str(exc),
                     "게이트웨이에 채팅 모델이 등록되어 있어야 합니다. 관리자에게 문의하세요.")

    if llm.model_source == "auto":
        return Check("model", "사용 중인 모델", OK,
                     f"{model} (게이트웨이 목록에서 자동으로 골랐습니다)")
    return Check("model", "사용 중인 모델", OK, f"{model} (설정된 값)")


def _check_mcp(settings: Settings, toolbox: McpToolbox) -> Check:
    if not settings.mcp_enabled:
        return Check("mcp", "도구 서버 (MCP)", WARN, "꺼져 있습니다. 문서 검색 기능이 없습니다.",
                     "환경변수 MCP_ENABLED를 지우거나 true로 두세요.")
    if not toolbox.available:
        return Check("mcp", "도구 서버 (MCP)", FAIL,
                     f"띄우지 못했습니다. {toolbox.last_error}".strip(),
                     "대화는 계속 됩니다. 문서 검색만 안 됩니다. 이건 앱 내부 문제이므로 "
                     "이미지를 만든 담당자에게 위 메시지를 그대로 전달하세요.")
    return Check("mcp", "도구 서버 (MCP)", OK, f"도구 {len(toolbox.tools)}개가 준비되어 있습니다.")


async def _check_documents(settings: Settings, toolbox: McpToolbox) -> tuple[Check, Check]:
    """벡터 DB와 임베딩을 한 번의 호출로 함께 봅니다.

    둘은 사실상 같은 경로라, 따로 물으면 같은 실패를 두 번 보고하게 됩니다.
    """
    off = Check("embedding", "임베딩", WARN, "벡터 DB가 없어 쓰이지 않습니다.")

    if not settings.vector_enabled:
        return (
            Check("vector", "벡터 DB (문서 검색)", WARN,
                  "설정되지 않았습니다. 대화는 되지만 문서를 올리고 찾는 기능이 없습니다.",
                  "Qdrant 애플리케이션을 설치한 뒤 환경변수 QDRANT_URL에 "
                  "http://<Qdrant 애플리케이션 ID>.<프로젝트 ID>.svc.cluster.local:6333 을 넣으세요."),
            off,
        )

    if not toolbox.available:
        return (
            Check("vector", "벡터 DB (문서 검색)", FAIL, "도구 서버가 없어 확인할 수 없습니다.",
                  "위의 도구 서버 항목을 먼저 보세요."),
            off,
        )

    try:
        info = await toolbox.call("collection_info", {})
    except Exception as exc:                                # noqa: BLE001
        info = f"[오류] {exc}"

    if info.startswith("[") or "=" not in info:
        # 도구가 돌려준 원문은 여러 줄일 수 있습니다. 화면에 그대로 쏟으면 읽히지
        # 않으므로 한 줄로 접습니다.
        reason = _one_line(info)
        # 임베딩 쪽에서 실패한 것인지 벡터 DB에서 실패한 것인지 갈라 줍니다 —
        # 고칠 곳이 완전히 다릅니다.
        if "sentence-transformers" in info or "임베딩" in info:
            return (
                Check("vector", "벡터 DB (문서 검색)", WARN, "임베딩이 준비되지 않아 확인하지 못했습니다."),
                Check("embedding", "임베딩", FAIL, reason,
                      "게이트웨이에 임베딩 모델이 있으면 EMBEDDING_PROVIDER=gateway 와 "
                      "EMBEDDING_MODEL_GATEWAY 를 설정하세요. 없으면 로컬 임베딩이 포함된 "
                      "이미지가 필요합니다 — 이미지를 만든 담당자에게 문의하세요."),
            )
        return (
            Check("vector", "벡터 DB (문서 검색)", FAIL, f"연결하지 못했습니다: {reason}",
                  f"주소가 {settings.qdrant_url} 로 되어 있습니다. 애플리케이션 목록에서 "
                  "Qdrant가 Healthy 인지, 그 애플리케이션 ID가 주소에 들어간 이름과 같은지 보세요."),
            Check("embedding", "임베딩", WARN, "벡터 DB에 닿지 못해 확인할 수 없습니다."),
        )

    fields = dict(_INFO.findall(info))
    points = fields.get("points", "?")
    embedder = fields.get("embedder", "?")

    vector = Check(
        "vector", "벡터 DB (문서 검색)", OK,
        f"연결됨. 컬렉션 {fields.get('collection', '?')} 에 조각 {points}개가 있습니다."
        + (" 아직 올린 문서가 없습니다." if points == "0" else ""),
    )

    where = "게이트웨이" if embedder.startswith("gateway:") else "앱 안에서 직접"
    embedding = Check("embedding", "임베딩", OK,
                      f"{where} 계산합니다. ({embedder}, {fields.get('dim', '?')}차원)")
    return vector, embedding
