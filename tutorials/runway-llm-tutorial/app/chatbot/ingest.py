"""문서를 청크로 나누기.

검색은 문서 단위가 아니라 **문단 단위**로 합니다. 문서 하나를 통째로 프롬프트에 넣으면
컨텍스트를 다 먹고, 모델은 관계없는 부분까지 읽느라 정확도가 떨어집니다.

두 가지만 신경 씁니다.

* **제목을 따라갑니다.** 마크다운 heading을 만나면 그 아래 청크에 제목을 붙여 둡니다.
  "3.2절이 뭐라고 하나?" 같은 질문이 통하려면 청크가 자기 위치를 알아야 합니다.
* **겹칩니다.** 청크 경계에 답이 걸치면 어느 쪽에서도 온전히 안 나옵니다.
  `CHUNK_OVERLAP`만큼 겹쳐서 그 확률을 낮춥니다.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

# 답 하나가 대체로 한 청크에 들어갈 만큼 크고, 여러 개가 프롬프트에 함께 들어갈 만큼 작게.
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")

# Qdrant의 포인트 ID는 부호 없는 정수이거나 UUID여야 합니다. 문자열 파일명은 못 씁니다.
# uuid5를 쓰면 같은 문서·같은 위치가 항상 같은 ID가 되므로, 다시 색인해도 중복이 아니라
# 덮어쓰기가 됩니다.
_NAMESPACE = uuid.UUID("6f1c1a3e-2f2b-4f8a-9f0a-1a2b3c4d5e6f")


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    heading: str
    index: int

    def to_point(self, vector: list[float]) -> dict:
        return {
            "id": self.id,
            "vector": vector,
            "payload": {
                "text": self.text,
                "source": self.source,
                "heading": self.heading,
                "index": self.index,
            },
        }


def chunk_document(text: str, source: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading = ""
    buffer: list[str] = []
    buffer_len = 0

    def flush() -> None:
        nonlocal buffer, buffer_len
        body = "\n".join(buffer).strip()
        if body:
            index = len(chunks)
            chunks.append(
                Chunk(
                    id=str(uuid.uuid5(_NAMESPACE, f"{source}#{index}")),
                    text=body,
                    source=source,
                    heading=heading,
                    index=index,
                )
            )
        # 다음 청크는 꼬리를 물고 시작합니다.
        tail = body[-CHUNK_OVERLAP:] if body else ""
        buffer = [tail] if tail else []
        buffer_len = len(tail)

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            # 제목은 경계입니다. 여기서 끊으면 청크가 한 주제만 담습니다.
            flush()
            heading = match.group(2)
            buffer = [line]
            buffer_len = len(line)
            continue

        buffer.append(line)
        buffer_len += len(line) + 1
        if buffer_len >= CHUNK_CHARS:
            flush()

    flush()
    return [c for c in chunks if c.text.strip()]


def safe_source_name(filename: str) -> str:
    """업로드 파일명을 그대로 신뢰하지 않습니다 — 경로 요소를 떼어 냅니다."""
    name = filename.replace("\\", "/").split("/")[-1].strip()
    return name or "untitled"
