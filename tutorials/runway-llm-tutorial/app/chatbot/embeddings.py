"""임베딩 — 문서와 질문을 같은 공간의 벡터로 바꾸는 부분.

경로가 둘입니다. **설치본마다 게이트웨이 구성이 다르기 때문**입니다.

* **게이트웨이**: `POST <LLM_BASE_URL>/embeddings`. 추가 의존성도, 다운로드도 없습니다.
  다만 기본 설치의 LiteLLM에는 임베딩 모델이 등록되어 있지 않을 수 있습니다 — 관리자가
  `litellm-config` ConfigMap에 직접 추가해야 생깁니다.
* **로컬**: `sentence-transformers`로 컨테이너 안에서 계산합니다. 게이트웨이 구성과
  무관하게 동작하지만 가중치를 한 번 내려받아야 하고, 그 캐시는 PVC에 둡니다.

`EMBEDDING_PROVIDER=auto`면 게이트웨이를 먼저 재보고 안 되면 로컬로 내려갑니다.
**어느 쪽을 쓰는지는 반드시 로그 한 줄로 남깁니다.** 검색 품질이 이상할 때 가장 먼저
확인할 것이 "지금 무엇으로 임베딩하고 있는가"인데, 조용히 폴백하면 그걸 알 수 없습니다.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

import httpx

from .config import Settings

logger = logging.getLogger("llmchat.embeddings")

# E5 계열은 문서와 질문에 서로 다른 접두사를 붙여 학습됐습니다. 붙이지 않아도 동작은
# 하지만 검색 품질이 눈에 띄게 떨어집니다. 모델을 바꾸면 이 규칙도 같이 봐야 합니다.
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "


class EmbeddingError(RuntimeError):
    pass


class Embedder(Protocol):
    name: str
    dim: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
    async def aclose(self) -> None: ...


class GatewayEmbedder:
    """LiteLLM의 OpenAI 호환 `/embeddings`."""

    def __init__(self, settings: Settings, model: str) -> None:
        self.name = f"gateway:{model}"
        self.dim = 0
        self._model = model
        self._batch = settings.embedding_batch_size
        self._client = httpx.AsyncClient(
            base_url=settings.llm_base_url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=httpx.Timeout(connect=settings.llm_connect_timeout, read=120.0, write=30.0, pool=30.0),
            verify=settings.ca_bundle or True,
        )

    async def _embed(self, inputs: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(inputs), self._batch):
            batch = inputs[start : start + self._batch]
            response = await self._client.post("/embeddings", json={"model": self._model, "input": batch})
            if response.status_code >= 400:
                raise EmbeddingError(
                    f"게이트웨이 임베딩 실패 {response.status_code}: {response.text[:300]}"
                )
            data = response.json().get("data", [])
            vectors.extend(item["embedding"] for item in data)
        if vectors:
            self.dim = len(vectors[0])
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts)

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text]))[0]

    async def aclose(self) -> None:
        await self._client.aclose()


class LocalEmbedder:
    """컨테이너 안에서 sentence-transformers로 계산합니다.

    모델 로딩과 인코딩은 CPU 바운드라 이벤트 루프를 막습니다. `asyncio.to_thread`로
    비켜 둡니다 — 이게 없으면 색인 중에 채팅 스트림이 멈춥니다.
    """

    def __init__(self, settings: Settings) -> None:
        self.name = f"local:{settings.embedding_model_local}"
        self._model_name = settings.embedding_model_local
        self._cache = settings.embedding_cache_dir
        self._batch = settings.embedding_batch_size
        self._model = None
        self.dim = 0

    async def _ensure_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "로컬 임베딩을 쓰려면 sentence-transformers가 필요합니다.\n"
                "  pip install -r requirements-local-embeddings.txt\n"
                "  또는 EMBEDDING_PROVIDER=gateway 로 게이트웨이 경로만 쓰세요."
            ) from exc

        logger.info("임베딩 모델을 로드합니다: %s (캐시 %s)", self._model_name, self._cache)
        self._model = await asyncio.to_thread(
            SentenceTransformer, self._model_name, cache_folder=self._cache
        )
        self.dim = int(self._model.get_sentence_embedding_dimension())
        return self._model

    async def _encode(self, texts: list[str]) -> list[list[float]]:
        model = await self._ensure_model()
        vectors = await asyncio.to_thread(
            model.encode, texts, batch_size=self._batch, normalize_embeddings=True
        )
        return [list(map(float, v)) for v in vectors]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._encode([E5_PASSAGE_PREFIX + t for t in texts])

    async def embed_query(self, text: str) -> list[float]:
        return (await self._encode([E5_QUERY_PREFIX + text]))[0]

    async def aclose(self) -> None:
        self._model = None


async def build_embedder(settings: Settings) -> Embedder:
    """설정과 실제 도달 가능성을 함께 보고 임베더를 고릅니다."""
    provider = settings.embedding_provider

    if provider in ("auto", "gateway") and settings.embedding_model_gateway:
        candidate = GatewayEmbedder(settings, settings.embedding_model_gateway)
        try:
            await candidate.embed_query("차원 확인")
            logger.info("임베딩: 게이트웨이 %s (dim=%d)", candidate.name, candidate.dim)
            return candidate
        except Exception as exc:            # noqa: BLE001 - 원인 그대로 남기고 폴백 판단
            await candidate.aclose()
            if provider == "gateway":
                raise EmbeddingError(
                    f"EMBEDDING_PROVIDER=gateway 인데 게이트웨이 임베딩이 실패했습니다: {exc}"
                ) from exc
            logger.warning("게이트웨이 임베딩 실패 → 로컬 모델로 내려갑니다: %s", exc)

    elif provider == "gateway":
        raise EmbeddingError("EMBEDDING_PROVIDER=gateway 인데 EMBEDDING_MODEL_GATEWAY가 비어 있습니다.")

    local = LocalEmbedder(settings)
    await local.embed_query("차원 확인")
    logger.info("임베딩: 로컬 %s (dim=%d)", local.name, local.dim)
    return local
