from collections.abc import Callable
from typing import Any

from tools.result import ToolResult, error_result
from tools.search.result_normalizer import normalize_results


WebSearchProvider = Callable[[str, int, dict[str, Any] | None], list[Any]]


def web_search(
    query: str,
    *,
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
    provider: WebSearchProvider | None = None,
) -> ToolResult:
    if not query.strip():
        return error_result("WEB_SEARCH_INVALID_QUERY", "query는 비어 있을 수 없습니다.")
    if provider is None:
        return error_result(
            "WEB_SEARCH_PROVIDER_REQUIRED",
            "Web 검색 provider가 아직 연결되지 않았습니다.",
        )

    try:
        return normalize_results("WEB", query, provider(query, top_k, filters))
    except Exception as exc:
        return error_result("WEB_SEARCH_FAILED", str(exc))
