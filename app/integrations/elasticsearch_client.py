"""Elasticsearch client used for product/transaction search and autocomplete."""
import os

from elasticsearch import AsyncElasticsearch

_client: AsyncElasticsearch | None = None


def get_es() -> AsyncElasticsearch:
    global _client
    if _client is None:
        _client = AsyncElasticsearch(
            os.environ["ELASTICSEARCH_URL"],
            api_key=os.environ.get("ELASTICSEARCH_API_KEY"),
            request_timeout=10,
        )
    return _client


async def index_document(index: str, doc_id: str, body: dict) -> dict:
    es = get_es()
    return await es.index(index=index, id=doc_id, document=body, refresh=False)


async def search_documents(index: str, query: dict, size: int = 20, from_: int = 0) -> dict:
    es = get_es()
    return await es.search(index=index, query=query, size=size, from_=from_)


async def suggest(index: str, prefix: str, field: str = "name.suggest", size: int = 8) -> list[str]:
    es = get_es()
    body = {
        "suggest": {
            "completions": {
                "prefix": prefix,
                "completion": {"field": field, "size": size, "skip_duplicates": True},
            }
        }
    }
    res = await es.search(index=index, body=body)
    options = (res.get("suggest", {}).get("completions", [{}])[0] or {}).get("options", [])
    return [o.get("text") for o in options if o.get("text")]


async def delete_by_query(index: str, query: dict) -> dict:
    es = get_es()
    return await es.delete_by_query(index=index, query=query, refresh=True)
