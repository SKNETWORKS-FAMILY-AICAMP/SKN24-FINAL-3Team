from typing import Any

from tools.result import ToolResult, error_result, success_result
from tools.search.search_schema import SearchResult


def normalize_results(
    search_type: str,
    query: str,
    results: list[Any],
) -> ToolResult:
    try:
        source = search_type.upper()
        if source not in {"RAG", "WEB"}:
            return error_result(
                "SEARCH_NORMALIZE_INVALID_SOURCE",
                f"허용되지 않은 검색 출처: {search_type}",
            )

        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(results):
            item = _to_mapping(item)
            if isinstance(item, dict):
                payload = item.get("payload") or item.get("metadata") or {}
                normalized.append(
                    SearchResult(
                        source=source,
                        id=item.get("id", index),
                        title=item.get("title") or payload.get("title") or "",
                        content=item.get("content")
                        or item.get("text")
                        or item.get("snippet")
                        or payload.get("content")
                        or payload.get("text")
                        or "",
                        url=item.get("url") or item.get("link") or payload.get("url"),
                        score=item.get("score"),
                        metadata=payload,
                    ).model_dump()
                )
            else:
                normalized.append(
                    SearchResult(source=source, id=index, content=str(item)).model_dump()
                )
        return success_result(
            {"query": query, "normalized_results": normalized}
        )
    except Exception as exc:
        return error_result("SEARCH_NORMALIZE_FAILED", str(exc))


def _to_mapping(item: Any) -> Any:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "dict"):
        return item.dict()
    if hasattr(item, "__dict__"):
        return vars(item)
    return item
