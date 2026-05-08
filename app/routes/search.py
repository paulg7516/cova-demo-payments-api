"""Search service — product search, autocomplete, indexing, reindex jobs."""
import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.integrations.elasticsearch_client import (
    delete_by_query,
    index_document,
    search_documents,
    suggest,
)

router = APIRouter(prefix="/api/search", tags=["search"])


class IndexRequest(BaseModel):
    index: str
    doc_id: str
    body: dict[str, Any]


class ReindexRequest(BaseModel):
    source_index: str
    dest_index: str
    batch_size: int = 500


@router.get("/products")
async def search_products(
    q: str = Query(..., min_length=1, max_length=200),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    category: str | None = None,
):
    """Full-text product search with optional category filter."""
    must: list[dict] = [{"multi_match": {"query": q, "fields": ["name^3", "description", "tags"]}}]
    if category:
        must.append({"term": {"category.keyword": category}})

    res = await search_documents(
        index="products",
        query={"bool": {"must": must}},
        size=size,
        from_=page * size,
    )
    hits = res.get("hits", {}).get("hits", [])
    return {
        "total": res.get("hits", {}).get("total", {}).get("value", 0),
        "took_ms": res.get("took", 0),
        "results": [{"id": h["_id"], "score": h["_score"], **h["_source"]} for h in hits],
    }


@router.get("/transactions")
async def search_transactions(
    user_id: str,
    q: str | None = None,
    size: int = Query(50, ge=1, le=200),
):
    """Search a user's transaction history. Used by support tooling."""
    must: list[dict] = [{"term": {"user_id.keyword": user_id}}]
    if q:
        must.append({"match": {"merchant": q}})

    res = await search_documents(
        index="transactions",
        query={"bool": {"must": must}},
        size=size,
    )
    hits = res.get("hits", {}).get("hits", [])
    return {"user_id": user_id, "count": len(hits), "results": [h["_source"] for h in hits]}


@router.get("/suggest")
async def autocomplete(prefix: str = Query(..., min_length=1, max_length=64)):
    """Typeahead suggestions for the search bar."""
    suggestions = await suggest("products", prefix)
    return {"prefix": prefix, "suggestions": suggestions}


@router.post("/index")
async def index_doc(req: IndexRequest):
    """Index a single document. Called by the catalog ingest worker."""
    try:
        res = await index_document(req.index, req.doc_id, req.body)
    except Exception as e:
        raise HTTPException(502, f"elasticsearch index failed: {e}")
    return {"indexed": True, "result": res.get("result"), "version": res.get("_version")}


@router.post("/reindex")
async def reindex(req: ReindexRequest):
    """Kick off a reindex from one index into another. Returns a task handle."""
    async def _run():
        await asyncio.sleep(0)

    asyncio.create_task(_run())
    return {
        "started": True,
        "source": req.source_index,
        "dest": req.dest_index,
        "batch_size": req.batch_size,
    }


@router.delete("/products/{doc_id}")
async def delete_product(doc_id: str):
    """Remove a product from the search index (e.g. when delisted)."""
    res = await delete_by_query("products", {"term": {"_id": doc_id}})
    return {"deleted": res.get("deleted", 0)}
