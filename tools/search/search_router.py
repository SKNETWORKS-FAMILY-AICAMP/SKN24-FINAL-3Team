from typing import Any

from tools.result import ToolResult, error_result, success_result
from tools.search.rag_search_tool import QdrantSearchClient, rag_search
from tools.search.search_schema import SearchTarget
from tools.search.web_search_tool import WebSearchProvider, web_search


def search(
    query: str,
    *,
    search_targets: SearchTarget = "RAG",
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    query_vector: list[float] | None = None,
    collection: str | None = None,
    rag_client: QdrantSearchClient | None = None,
    web_provider: WebSearchProvider | None = None,
) -> ToolResult:
    target = search_targets.upper()
    if target == "NONE":
        return success_result({"query": query, "normalized_results": []})
    if target == "RAG":
        return rag_search(
            query,
            query_vector=query_vector,
            filters=filters,
            top_k=top_k,
            collection=collection,
            client=rag_client,
        )
    if target == "WEB":
        return web_search(query, filters=filters, top_k=top_k, provider=web_provider)
    if target == "BOTH":
        rag_result = rag_search(
            query,
            query_vector=query_vector,
            filters=filters,
            top_k=top_k,
            collection=collection,
            client=rag_client,
        )
        web_result = web_search(
            query,
            filters=filters,
            top_k=top_k,
            provider=web_provider,
        )
        if not rag_result["success"] and not web_result["success"]:
            return error_result(
                "SEARCH_BOTH_FAILED",
                "RAG 및 Web 검색이 모두 실패했습니다.",
                {"rag": rag_result["error"], "web": web_result["error"]},
            )
        normalized_results = []
        for result in (rag_result, web_result):
            if result["success"]:
                normalized_results.extend(result["data"]["normalized_results"])
        return success_result({"query": query, "normalized_results": normalized_results})
    return error_result("INVALID_SEARCH_TARGET", f"허용되지 않은 검색 대상: {search_targets}")
