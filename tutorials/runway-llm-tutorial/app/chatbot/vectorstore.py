"""Qdrant REST 클라이언트.

`qdrant-client` 패키지를 쓰지 않고 httpx로 직접 부릅니다. 이유는 튜토리얼이라서입니다 —
여기 있는 요청은 전부 `curl`로 똑같이 재현할 수 있고, 그래야 "지금 무슨 일이
일어났는지"를 Code Server 터미널에서 눈으로 확인할 수 있습니다.

Runway 2.3.0의 Qdrant 애플리케이션 템플릿에 대해 알아 둘 것:

* 인클러스터 주소는 `http://<릴리스명>.<프로젝트>.svc.cluster.local:6333` (REST),
  6334는 gRPC입니다.
* **API 키가 없습니다.** 템플릿은 `apiKey`를 노출하지 않고, 켜져 있지도 않습니다.
  그리고 외부 노출(HTTPRoute)을 켜도 플랫폼 로그인이 앞에 붙지 않습니다.
  → 이 튜토리얼은 외부 접근을 끈 채 인클러스터로만 씁니다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("llmchat.vectorstore")


class VectorStoreError(RuntimeError):
    pass


@dataclass
class Hit:
    score: float
    text: str
    source: str
    heading: str


class QdrantStore:
    def __init__(self, base_url: str, collection: str, *, timeout: float = 30.0) -> None:
        self.collection = collection
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise VectorStoreError(
                f"Qdrant에 연결하지 못했습니다: {self._client.base_url}\n"
                "  인클러스터 주소는 프로젝트 네임스페이스 안에서만 풀립니다.\n"
                "  로컬에서 실험 중이라면 `kubectl -n <프로젝트> port-forward svc/<릴리스명> 6333:6333`."
            ) from exc
        if response.status_code >= 400:
            raise VectorStoreError(f"Qdrant {method} {path} → {response.status_code}: {response.text[:400]}")
        return response.json()

    # -- 컬렉션 ---------------------------------------------------------------

    async def ping(self) -> None:
        """닿는지만 확인합니다.

        임베더를 만들기 **전에** 부릅니다. 순서가 반대면, Qdrant 주소가 틀렸을 때
        임베딩 쪽 오류가 먼저 터져서 사용자가 엉뚱한 곳을 고치게 됩니다.
        """
        await self._request("GET", "/collections")

    async def collection_exists(self) -> bool:
        response = await self._client.get(f"/collections/{self.collection}")
        return response.status_code == 200

    async def ensure_collection(self, dim: int) -> bool:
        """없으면 만듭니다. 새로 만들었으면 True.

        **벡터 차원은 컬렉션을 만들 때 고정됩니다.** 임베딩 모델을 바꾸면 차원이 달라지고,
        기존 컬렉션에 넣으려 하면 Qdrant가 거부합니다. 그때 할 일은 컬렉션을 지우고 다시
        색인하는 것입니다 — 여기서 차원을 확인해 어긋나면 이름을 대며 알려 줍니다.
        """
        response = await self._client.get(f"/collections/{self.collection}")
        if response.status_code == 200:
            existing = response.json()["result"]["config"]["params"]["vectors"]["size"]
            if existing != dim:
                raise VectorStoreError(
                    f"컬렉션 '{self.collection}'의 벡터 차원은 {existing}인데 지금 임베더는 {dim}차원입니다.\n"
                    "  임베딩 모델을 바꾸면 컬렉션을 다시 만들어야 합니다:\n"
                    f"    curl -X DELETE <QDRANT_URL>/collections/{self.collection}"
                )
            return False

        await self._request(
            "PUT",
            f"/collections/{self.collection}",
            json={"vectors": {"size": dim, "distance": "Cosine"}},
        )
        logger.info("컬렉션 %s 생성 (dim=%d, Cosine)", self.collection, dim)
        return True

    async def drop_collection(self) -> None:
        await self._client.delete(f"/collections/{self.collection}")

    async def count(self) -> int:
        result = await self._request("POST", f"/collections/{self.collection}/points/count", json={"exact": True})
        return int(result["result"]["count"])

    # -- 쓰기 -----------------------------------------------------------------

    async def upsert(self, points: list[dict[str, Any]]) -> None:
        """`wait=true`로 씁니다 — 색인 직후 검색이 비어 나오는 혼란을 없애려는 것입니다."""
        await self._request(
            "PUT",
            f"/collections/{self.collection}/points",
            params={"wait": "true"},
            json={"points": points},
        )

    async def delete_by_source(self, source: str) -> None:
        await self._request(
            "POST",
            f"/collections/{self.collection}/points/delete",
            params={"wait": "true"},
            json={"filter": {"must": [{"key": "source", "match": {"value": source}}]}},
        )

    # -- 읽기 -----------------------------------------------------------------

    async def query(self, vector: list[float], top_k: int) -> list[Hit]:
        result = await self._request(
            "POST",
            f"/collections/{self.collection}/points/query",
            json={"query": vector, "limit": top_k, "with_payload": True},
        )
        hits: list[Hit] = []
        for point in result["result"]["points"]:
            payload = point.get("payload") or {}
            hits.append(
                Hit(
                    score=float(point.get("score", 0.0)),
                    text=payload.get("text", ""),
                    source=payload.get("source", "?"),
                    heading=payload.get("heading", ""),
                )
            )
        return hits

    async def list_sources(self) -> list[dict[str, Any]]:
        """색인된 문서 이름과 청크 수. 페이로드만 훑으므로 벡터는 받지 않습니다."""
        counts: dict[str, int] = {}
        offset: Any = None
        while True:
            body: dict[str, Any] = {"limit": 256, "with_payload": ["source"], "with_vector": False}
            if offset is not None:
                body["offset"] = offset
            result = await self._request("POST", f"/collections/{self.collection}/points/scroll", json=body)
            for point in result["result"]["points"]:
                source = (point.get("payload") or {}).get("source", "?")
                counts[source] = counts.get(source, 0) + 1
            offset = result["result"].get("next_page_offset")
            if offset is None:
                break
        return [{"source": name, "chunks": n} for name, n in sorted(counts.items())]


def format_hits(hits: list[Hit]) -> str:
    """검색 결과를 모델에게 넘길 텍스트로.

    출처를 각 발췌 앞에 붙이는 이유는 두 가지입니다 — 모델이 답에 출처를 인용할 수 있고,
    사람이 답을 검증할 수 있습니다.
    """
    if not hits:
        return "검색 결과가 없습니다."
    blocks = []
    for i, hit in enumerate(hits, 1):
        title = f"{hit.source}" + (f" › {hit.heading}" if hit.heading else "")
        blocks.append(f"[{i}] {title} (유사도 {hit.score:.3f})\n{hit.text}")
    return "\n\n".join(blocks)
