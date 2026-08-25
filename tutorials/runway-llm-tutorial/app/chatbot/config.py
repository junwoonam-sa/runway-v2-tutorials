"""설정 로딩.

원칙 하나만 기억하면 됩니다 — **그럴듯한 기본값을 두지 않습니다.**

`LLM_BASE_URL`에 기본값을 넣어 두면, 값을 빠뜨린 사람은 시작 시점이 아니라 첫 메시지에서
DNS 오류나 404를 만납니다. 설정 누락이 네트워크 장애처럼 보이면 원인을 찾는 데 몇 배가
걸립니다. 그래서 필수값이 없으면 **이름을 대며 즉시 종료**합니다.

값을 읽는 순서 (뒤가 이깁니다):

    1. .env                       로컬 개발 편의용
    2. /vault/secrets/*.env       OpenBao Vault Agent가 주입한 파일 (Stage 0~1)
    3. 실제 환경변수              차트가 Secret/env로 넣어 준 값

2번이 이 튜토리얼의 핵심입니다. Code Server든 배포된 앱이든, 시크릿은 이미지에도
values.yaml에도 들어가지 않고 파일로 주입됩니다.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("llmchat.config")

# OpenBao Vault Agent가 렌더한 파일이 놓이는 곳. 차트가 붙이는 어노테이션
# `vault.hashicorp.com/agent-inject-secret-<name>.env` 의 렌더 결과입니다.
DEFAULT_VAULT_SECRETS_DIR = "/vault/secrets"


class ConfigError(RuntimeError):
    """필수 설정이 빠졌을 때. 메시지에 빠진 이름이 전부 들어갑니다.

    웹 서버는 이걸 올리지 않습니다 — 아래 `Problem` 설명 참고. 개발용 진입점과
    MCP 서버처럼 **사람이 터미널을 보고 있는** 경로에서만 씁니다.
    """


@dataclass(frozen=True)
class Problem:
    """설정에 빠졌거나 잘못된 것 하나.

    예외를 던지는 대신 이걸 모으는 이유:

    예외를 던지면 프로세스가 죽고, 클러스터에서는 파드가 CrashLoopBackOff가 됩니다.
    그러면 원인은 `kubectl logs`에만 남고 **화면은 아예 뜨지 않습니다.** 터미널을
    쓰지 않는 사람에게는 무엇이 잘못됐는지 알 방법이 없다는 뜻입니다.

    그래서 앱은 항상 뜨고, 무엇이 빠졌는지 화면에서 말합니다. 그럴듯한 기본값을
    채워 넣는 것이 아닙니다 — 값은 비어 있는 채로 남고, 채팅도 막힙니다.
    달라지는 것은 **실패가 보이는 장소**뿐입니다. 로그에는 같은 내용이 그대로
    남으므로 터미널을 보는 사람의 경험은 바뀌지 않습니다.
    """

    key: str          # 설정 이름 (LLM_API_KEY 등)
    severity: str     # "fail" — 이게 있으면 채팅 불가 | "warn" — 일부 기능만 꺼짐
    symptom: str      # 지금 무슨 상태인지, 사람이 읽는 말로
    fix: str          # 무엇을 하면 되는지

    def as_dict(self) -> dict:
        return {"key": self.key, "severity": self.severity, "symptom": self.symptom, "fix": self.fix}


def _parse_env_file(path: Path) -> dict[str, str]:
    """`KEY=VALUE` 한 줄씩. 주석과 빈 줄은 건너뜁니다.

    Vault Agent 템플릿이 KV-v2의 `data.data` 맵을 이 형식으로 펼쳐 줍니다.
    """
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        # 사람이 손으로 쓴 .env에는 따옴표가 섞입니다. Vault가 쓴 파일에는 없습니다.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    return out


def _collect_environment(vault_dir: str, dotenv: str = ".env") -> dict[str, str]:
    merged: dict[str, str] = {}

    dotenv_path = Path(dotenv)
    if dotenv_path.is_file():
        merged.update(_parse_env_file(dotenv_path))
        logger.info("read %s", dotenv_path)

    secrets_dir = Path(vault_dir)
    if secrets_dir.is_dir():
        for path in sorted(secrets_dir.glob("*.env")):
            merged.update(_parse_env_file(path))
            # 값은 절대 찍지 않습니다. 어떤 파일에서 몇 개를 읽었는지만 남깁니다.
            logger.info("read injected secret %s", path)
    else:
        logger.info("no injected secrets at %s (this is normal outside the cluster)", vault_dir)

    merged.update(os.environ)
    return merged


def _flag(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- LLM 게이트웨이 (필수 3개) ---------------------------------------------
    llm_base_url: str
    llm_model: str
    llm_api_key: str

    llm_temperature: float = 0.7
    llm_max_tokens: int = 0          # 0 = 모델 기본값에 맡김
    llm_connect_timeout: float = 10.0
    llm_read_timeout: float = 300.0
    system_prompt: str = ""

    # 툴 콜 왕복 상한. 모델이 계속 툴만 부르며 도는 것을 막습니다.
    max_tool_rounds: int = 3

    # 대화 이력 상한. 서버는 상태를 갖지 않으므로, 이것은 "기억"이 아니라
    # "한 요청으로 받아 줄 양"의 한계입니다.
    max_history_messages: int = 40
    max_message_chars: int = 16000

    # --- 벡터 DB (Qdrant) ------------------------------------------------------
    # 비어 있으면 벡터 기능 전체가 꺼집니다. Stage 3까지는 비워 두고 진행합니다.
    qdrant_url: str = ""
    qdrant_collection: str = "tutorial-docs"

    # --- 임베딩 ----------------------------------------------------------------
    # auto: 게이트웨이를 먼저 시도하고 실패하면 로컬 모델로 내려갑니다.
    embedding_provider: str = "auto"          # auto | gateway | local
    embedding_model_gateway: str = ""
    embedding_model_local: str = "intfloat/multilingual-e5-small"
    embedding_cache_dir: str = "/data/embedding-cache"
    embedding_batch_size: int = 32

    # --- MCP -------------------------------------------------------------------
    # 서버를 이 컨테이너 안에서 자식 프로세스로 띄웁니다. 네트워크에 아무것도
    # 노출되지 않습니다 — 표준입출력으로만 이야기합니다.
    mcp_enabled: bool = True
    mcp_command: list[str] = field(default_factory=list)

    # --- 기타 ------------------------------------------------------------------
    data_dir: str = "/data"
    access_password: str = ""
    ca_bundle: str = ""

    # 설정에서 발견한 문제들. 비어 있으면 정상입니다.
    problems: tuple[Problem, ...] = ()

    @property
    def vector_enabled(self) -> bool:
        return bool(self.qdrant_url)

    @property
    def blockers(self) -> tuple[Problem, ...]:
        """이게 있으면 채팅을 시작할 수 없습니다."""
        return tuple(p for p in self.problems if p.severity == "fail")

    def public_view(self) -> dict:
        """UI에 내려보내도 되는 것만. 키와 URL은 포함하지 않습니다."""
        return {
            "model": self.llm_model,
            "vectorEnabled": self.vector_enabled,
            "collection": self.qdrant_collection if self.vector_enabled else None,
            "mcpEnabled": self.mcp_enabled,
            "passwordRequired": bool(self.access_password),
        }


def load_settings(vault_dir: str | None = None) -> Settings:
    """항상 Settings를 돌려줍니다. 문제는 예외가 아니라 `settings.problems`로.

    이유는 `Problem`의 설명을 보세요 — 요약하면, 죽은 파드는 아무것도 알려 주지
    못하기 때문입니다.
    """
    env = _collect_environment(vault_dir or os.environ.get("VAULT_SECRETS_DIR", DEFAULT_VAULT_SECRETS_DIR))
    problems: list[Problem] = []

    base_url = (env.get("LLM_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        problems.append(Problem(
            key="LLM_BASE_URL",
            severity="fail",
            symptom="LLM 게이트웨이 주소가 설정되지 않았습니다.",
            fix="환경변수 LLM_BASE_URL을 넣으세요. 같은 프로젝트 안에서는 "
                "http://litellm.runway-applications.svc.cluster.local:4000/v1 입니다.",
        ))
    elif not base_url.endswith("/v1"):
        problems.append(Problem(
            key="LLM_BASE_URL",
            severity="fail",
            symptom=f"게이트웨이 주소가 '/v1'로 끝나지 않습니다: {base_url}",
            fix="주소 끝에 /v1 을 붙이세요. 호출 경로가 <주소>/chat/completions 이기 때문입니다.",
        ))

    api_key = (env.get("LLM_API_KEY") or "").strip()
    if not api_key:
        problems.append(Problem(
            key="LLM_API_KEY",
            severity="fail",
            symptom="LLM API 키가 없습니다. 게이트웨이에 요청을 보낼 수 없습니다.",
            fix="Runway 콘솔 → 계정 설정 → 액세스 키(Access keys) → LLM API 키(LLM API Keys) → 생성. "
                "그 값을 OpenBao 시크릿의 LLM_API_KEY 항목에 저장하세요.",
        ))
    elif not api_key.startswith("sk-"):
        # Runway API 키(오프라인 토큰, 'eyJ...')를 여기 넣는 실수가 잦습니다.
        # 게이트웨이는 그 키를 모르고, 증상은 401 하나뿐이라 원인이 드러나지 않습니다.
        problems.append(Problem(
            key="LLM_API_KEY",
            severity="fail",
            symptom="LLM API 키의 모양이 다릅니다. 'sk-'로 시작해야 하는데 그렇지 않습니다.",
            fix="키가 세 종류라 헷갈리기 쉽습니다. 'API 키'(eyJ로 시작)가 아니라 "
                "'LLM API 키'(sk-로 시작)여야 합니다. 콘솔의 같은 화면에서 탭이 다릅니다.",
        ))

    provider = (env.get("EMBEDDING_PROVIDER") or "auto").lower()
    if provider not in {"auto", "gateway", "local"}:
        problems.append(Problem(
            key="EMBEDDING_PROVIDER",
            severity="fail",
            symptom=f"EMBEDDING_PROVIDER 값이 잘못되었습니다: {provider!r}",
            fix="auto, gateway, local 중 하나여야 합니다. 잘 모르겠으면 auto로 두세요.",
        ))
        provider = "auto"

    # LLM_MODEL은 필수가 아닙니다 — 비어 있으면 기동할 때 게이트웨이에 물어봅니다.
    # 게이트웨이가 publish한 이름은 관리자가 손으로 적어 넣은 문자열이라 추측할 수
    # 없고, 그걸 알아내라고 요구하는 것이 첫 실패의 가장 흔한 원인이었습니다.
    model = (env.get("LLM_MODEL") or "").strip()

    mcp_command = env.get("MCP_COMMAND", "").split()
    if not mcp_command:
        # 같은 인터프리터로 같은 이미지 안의 모듈을 띄웁니다. 배포물이 하나로 유지됩니다.
        mcp_command = [sys.executable, "-m", "mcp_server.server"]

    settings = Settings(
        llm_base_url=base_url,
        llm_model=model,
        llm_api_key=api_key,
        llm_temperature=float(env.get("LLM_TEMPERATURE") or 0.7),
        llm_max_tokens=int(env.get("LLM_MAX_TOKENS") or 0),
        llm_connect_timeout=float(env.get("LLM_CONNECT_TIMEOUT") or 10),
        llm_read_timeout=float(env.get("LLM_READ_TIMEOUT") or 300),
        system_prompt=env.get("LLM_SYSTEM_PROMPT", ""),
        max_tool_rounds=int(env.get("LLM_MAX_TOOL_ROUNDS") or 3),
        max_history_messages=int(env.get("LLM_MAX_HISTORY_MESSAGES") or 40),
        max_message_chars=int(env.get("LLM_MAX_MESSAGE_CHARS") or 16000),
        qdrant_url=(env.get("QDRANT_URL") or "").rstrip("/"),
        qdrant_collection=env.get("QDRANT_COLLECTION") or "tutorial-docs",
        embedding_provider=provider,
        embedding_model_gateway=env.get("EMBEDDING_MODEL_GATEWAY", ""),
        embedding_model_local=env.get("EMBEDDING_MODEL_LOCAL") or "intfloat/multilingual-e5-small",
        embedding_cache_dir=env.get("EMBEDDING_CACHE_DIR") or "/data/embedding-cache",
        embedding_batch_size=int(env.get("EMBEDDING_BATCH_SIZE") or 32),
        mcp_enabled=_flag(env.get("MCP_ENABLED"), True),
        mcp_command=mcp_command,
        data_dir=env.get("DATA_DIR") or "/data",
        access_password=env.get("ACCESS_PASSWORD", ""),
        ca_bundle=env.get("CA_BUNDLE", ""),
        problems=tuple(problems),
    )

    # 로그에는 지금까지와 똑같이 남깁니다. 터미널을 보는 사람의 경험은 바뀌지 않습니다.
    for problem in problems:
        logger.error("[%s] %s → %s", problem.key, problem.symptom, problem.fix)

    _sanitise_ca_bundle(settings)
    return settings


def load_settings_strict(vault_dir: str | None = None) -> Settings:
    """문제가 있으면 예외로 즉시 실패합니다.

    사람이 터미널을 보고 있는 경로 전용입니다 — 개발용 진입점과 MCP 서버.
    거기서는 즉시 죽는 편이 낫습니다. 웹 서버는 `load_settings`를 씁니다.
    """
    settings = load_settings(vault_dir)
    if settings.blockers:
        raise ConfigError(
            "\n".join(f"  [{p.key}] {p.symptom}\n      → {p.fix}" for p in settings.blockers)
        )
    return settings


def _sanitise_ca_bundle(settings: Settings) -> None:
    """가리키는 파일이 없는 CA 번들 환경변수를 지웁니다.

    사설 CA를 쓰는 설치본에서 `platform-root-ca` Secret을 optional로 마운트하면,
    Secret이 없을 때 **파일은 없는데 환경변수만 남는** 상태가 됩니다. 그 상태에서
    requests 계열은 기본 신뢰 저장소로 넘어가지 않고 그냥 실패합니다. 증상이
    "인증서 오류"라 CA를 의심하게 되는데 진짜 원인은 없는 경로입니다.
    """
    for name in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE"):
        path = os.environ.get(name)
        if path and not Path(path).is_file():
            logger.warning("%s가 없는 파일 %s 를 가리켜 변수를 제거합니다", name, path)
            os.environ.pop(name, None)

    if settings.ca_bundle and not Path(settings.ca_bundle).is_file():
        logger.warning("CA_BUNDLE %s 가 없어 기본 신뢰 저장소를 씁니다", settings.ca_bundle)
