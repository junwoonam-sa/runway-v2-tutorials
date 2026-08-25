"""가짜 Qdrant — 메모리에만 사는, 이 앱이 쓰는 엔드포인트만 있는 대역.

Stage 4를 노트북에서 미리 밟아 보기 위한 것입니다. 진짜 Qdrant는 프로젝트에 애플리케이션
으로 설치하고, 이건 그 전에 배선을 확인하는 용도입니다.

    PUT    /collections/{c}
    GET    /collections/{c}
    PUT    /collections/{c}/points
    POST   /collections/{c}/points/query
    POST   /collections/{c}/points/scroll
    POST   /collections/{c}/points/count
    POST   /collections/{c}/points/delete
    DELETE /collections/{c}

    python scripts/stub_qdrant.py             # :6333

검색은 코사인 유사도를 그대로 계산합니다 — 데이터가 적으면 이게 정확히 맞고, 많아지면
느려집니다. 진짜 Qdrant가 하는 일(HNSW 색인, 디스크 영속, 필터 최적화)은 여기 없습니다.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="stub Qdrant")

# {컬렉션: {"size": int, "points": {id: {"vector": [...], "payload": {...}}}}}
STORE: dict[str, dict] = {}


@app.get("/collections")
async def list_collections():
    """앱이 '닿는지'를 확인할 때 부르는 경로입니다. 진짜 Qdrant에도 있습니다."""
    return {"result": {"collections": [{"name": n} for n in STORE]}, "status": "ok"}


@app.put("/collections/{name}")
async def create_collection(name: str, request: Request):
    body = await request.json()
    STORE[name] = {"size": body["vectors"]["size"], "points": {}}
    return {"result": True, "status": "ok"}


@app.get("/collections/{name}")
async def get_collection(name: str):
    if name not in STORE:
        return JSONResponse(status_code=404, content={"status": {"error": "Not found"}})
    return {"result": {"config": {"params": {"vectors": {"size": STORE[name]["size"]}}}}}


@app.delete("/collections/{name}")
async def drop_collection(name: str):
    STORE.pop(name, None)
    return {"result": True, "status": "ok"}


@app.put("/collections/{name}/points")
async def upsert(name: str, request: Request):
    body = await request.json()
    collection = STORE.setdefault(name, {"size": 0, "points": {}})
    for point in body["points"]:
        if collection["size"] and len(point["vector"]) != collection["size"]:
            return JSONResponse(
                status_code=400,
                content={"status": {"error": f"expected dim {collection['size']}, got {len(point['vector'])}"}},
            )
        collection["points"][point["id"]] = {"vector": point["vector"], "payload": point.get("payload", {})}
    return {"result": {"status": "completed"}, "status": "ok"}


@app.post("/collections/{name}/points/query")
async def query(name: str, request: Request):
    body = await request.json()
    vector = body["query"]
    limit = body.get("limit", 5)
    points = STORE.get(name, {}).get("points", {})

    scored = sorted(
        ({"id": pid, "score": _cosine(vector, p["vector"]), "payload": p["payload"]} for pid, p in points.items()),
        key=lambda item: item["score"],
        reverse=True,
    )
    return {"result": {"points": scored[:limit]}}


@app.post("/collections/{name}/points/scroll")
async def scroll(name: str, request: Request):
    points = STORE.get(name, {}).get("points", {})
    return {
        "result": {
            "points": [{"id": pid, "payload": p["payload"]} for pid, p in points.items()],
            "next_page_offset": None,
        }
    }


@app.post("/collections/{name}/points/count")
async def count(name: str):
    return {"result": {"count": len(STORE.get(name, {}).get("points", {}))}}


@app.post("/collections/{name}/points/delete")
async def delete(name: str, request: Request):
    body = await request.json()
    conditions = body.get("filter", {}).get("must", [])
    points = STORE.get(name, {}).get("points", {})
    for condition in conditions:
        key, want = condition["key"], condition["match"]["value"]
        for pid in [pid for pid, p in points.items() if p["payload"].get(key) == want]:
            points.pop(pid)
    return {"result": {"status": "completed"}, "status": "ok"}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(y * y for y in b) ** 0.5 or 1.0
    return dot / (na * nb)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=6333, log_level="warning")
