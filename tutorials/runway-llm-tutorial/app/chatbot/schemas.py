"""요청/응답 스키마.

서버는 대화를 저장하지 않습니다. 클라이언트가 매번 전체 이력을 보내고, 서버는 그것을
검사한 뒤 게이트웨이로 넘깁니다. 파드가 재시작해도 대화가 사라지지 않고, 복제본을 늘려도
세션 고정이 필요 없습니다 — 대신 이력이 길수록 요청이 커집니다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
