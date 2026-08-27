"""요청/응답 스키마.

서버는 대화를 저장하지 않습니다. 클라이언트가 매번 전체 이력을 보내고, 서버는 그것을
검사한 뒤 게이트웨이로 넘깁니다. 파드가 재시작해도 대화가 사라지지 않고, 복제본을 늘려도
세션 고정이 필요 없습니다 — 대신 이력이 길수록 요청이 커집니다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 사용자가 화면에서 적는 지시의 길이 상한. 프롬프트가 길수록 매 요청의 비용이 늘고,
# 대화 이력이 밀려날 수 있어 상한을 둡니다.
MAX_SYSTEM_PROMPT_CHARS = 4000


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """서버는 대화도, 지시도 저장하지 않습니다. 매 요청에 함께 옵니다."""

    model_config = ConfigDict(populate_by_name=True)

    messages: list[Message] = Field(min_length=1)

    # 화면에서 적은 지시. 배포가 정한 시스템 프롬프트를 대체하지 않고 **뒤에** 붙습니다
    # (agent.build_messages 참고). 브라우저에만 저장되므로 사람마다 다를 수 있습니다.
    system_prompt: str = Field(
        default="", alias="systemPrompt", max_length=MAX_SYSTEM_PROMPT_CHARS
    )
