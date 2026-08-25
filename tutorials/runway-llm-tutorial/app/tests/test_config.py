"""설정 로딩 — 특히 "빠진 값을 이름으로, 고치는 법과 함께 알려 주는가".

핵심 규칙이 하나 바뀌었습니다. 웹 서버 경로에서는 **예외를 던지지 않습니다.**
죽은 파드는 아무것도 알려 주지 못하고, 터미널을 쓰지 않는 사람에게는 화면이 안 뜨는
것이 곧 "원인을 알 수 없음"이기 때문입니다. 대신 문제를 모아서 화면으로 보냅니다.

터미널을 보고 있는 경로(개발용 진입점, MCP 서버)는 여전히 즉시 실패합니다 —
`load_settings_strict`.
"""

from __future__ import annotations

import pytest

from chatbot.config import ConfigError, load_settings, load_settings_strict


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for name in (
        "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "QDRANT_URL",
        "EMBEDDING_PROVIDER", "MCP_ENABLED", "ACCESS_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)          # 실수로 저장소의 .env를 읽지 않도록
    return tmp_path


def problems_by_key(settings) -> dict:
    return {p.key: p for p in settings.problems}


def test_missing_values_become_problems_not_exceptions(clean_env):
    """앱은 떠야 합니다. 무엇이 빠졌는지는 화면이 말합니다."""
    settings = load_settings(vault_dir=str(clean_env / "nope"))

    found = problems_by_key(settings)
    assert "LLM_BASE_URL" in found
    assert "LLM_API_KEY" in found
    assert all(p.severity == "fail" for p in settings.blockers)


def test_every_problem_says_how_to_fix_it(clean_env):
    """`fix`가 비어 있으면 이 구조는 의미가 없습니다 — 다음 행동을 정해 주지 못합니다."""
    settings = load_settings(vault_dir=str(clean_env / "nope"))
    for problem in settings.problems:
        assert problem.symptom.strip(), problem.key
        assert problem.fix.strip(), problem.key


def test_the_api_key_fix_names_the_right_console_tab(clean_env):
    """키가 세 종류라, '어디서 발급하는지'까지 말해야 실제로 도움이 됩니다."""
    settings = load_settings(vault_dir=str(clean_env / "nope"))
    fix = problems_by_key(settings)["LLM_API_KEY"].fix
    assert "액세스 키" in fix and "LLM API 키" in fix


def test_runway_api_key_shape_is_caught(clean_env, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://litellm:4000/v1")
    monkeypatch.setenv("LLM_API_KEY", "eyJhbGciOiJIUzUxMiJ9.stub")   # Runway API 키 모양

    problem = problems_by_key(load_settings(vault_dir=str(clean_env / "nope")))["LLM_API_KEY"]
    assert problem.severity == "fail"
    assert "sk-" in problem.symptom


def test_model_is_optional(clean_env, monkeypatch):
    """모델 이름은 추측할 수 없는 값이라 필수로 두지 않습니다 — 앱이 물어봅니다."""
    monkeypatch.setenv("LLM_BASE_URL", "http://litellm:4000/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    settings = load_settings(vault_dir=str(clean_env / "nope"))
    assert settings.llm_model == ""
    assert settings.blockers == ()          # 모델이 없다고 채팅을 막지는 않습니다


def test_base_url_without_v1_is_caught(clean_env, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.com")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    problem = problems_by_key(load_settings(vault_dir=str(clean_env / "nope")))["LLM_BASE_URL"]
    assert "/v1" in problem.fix


def test_injected_secret_file_is_read(clean_env, monkeypatch):
    vault = clean_env / "vault"
    vault.mkdir()
    (vault / "llmchat.env").write_text(
        "LLM_API_KEY=sk-from-openbao\nQDRANT_URL=http://qdrant:6333\n", encoding="utf-8"
    )
    monkeypatch.setenv("LLM_BASE_URL", "http://litellm:4000/v1")

    settings = load_settings(vault_dir=str(vault))
    assert settings.llm_api_key == "sk-from-openbao"
    assert settings.vector_enabled is True
    assert settings.blockers == ()


def test_real_environment_beats_the_injected_file(clean_env, monkeypatch):
    vault = clean_env / "vault"
    vault.mkdir()
    (vault / "llmchat.env").write_text("LLM_API_KEY=sk-from-file\n", encoding="utf-8")
    monkeypatch.setenv("LLM_BASE_URL", "http://litellm:4000/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-from-env")

    assert load_settings(vault_dir=str(vault)).llm_api_key == "sk-from-env"


def test_vector_features_are_off_without_qdrant_url(clean_env, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://litellm:4000/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-x")

    settings = load_settings(vault_dir=str(clean_env / "nope"))
    assert settings.vector_enabled is False
    assert settings.public_view()["collection"] is None


def test_strict_loader_still_raises_for_terminal_callers(clean_env):
    """MCP 서버와 개발용 진입점은 사람이 터미널을 보고 있으므로 즉시 실패가 낫습니다."""
    with pytest.raises(ConfigError) as exc:
        load_settings_strict(vault_dir=str(clean_env / "nope"))

    message = str(exc.value)
    assert "LLM_BASE_URL" in message and "LLM_API_KEY" in message
    assert "→" in message                    # 증상만이 아니라 조치도 들어 있어야 합니다


def test_strict_loader_passes_when_configured(clean_env, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://litellm:4000/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    assert load_settings_strict(vault_dir=str(clean_env / "nope")).llm_api_key == "sk-test"
