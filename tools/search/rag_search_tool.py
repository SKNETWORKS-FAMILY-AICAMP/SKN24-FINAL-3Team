from typing import Any, Protocol

from config.settings import Settings, get_settings
from tools.result import ToolResult, error_result
from tools.search.result_normalizer import normalize_results


class QdrantSearchClient(Protocol):
    def query_points(self, **kwargs: Any) -> Any: ...


def rag_search(
    query: str,
    *,
    query_vector: list[float] | None = None,
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    collection: str | None = None,
    client: QdrantSearchClient | None = None,
    settings: Settings | None = None,
) -> ToolResult:
    if not query.strip():
        return error_result("RAG_INVALID_QUERY", "query는 비어 있을 수 없습니다.")
    if not query_vector:
        return error_result(
            "RAG_QUERY_VECTOR_REQUIRED",
            "Qdrant 검색에는 query_vector가 필요합니다.",
        )

    settings = settings or get_settings()
    selected_collection = collection or settings.qdrant_collection

    try:
        qdrant = client or _create_qdrant_client(settings.qdrant_url)
        response = qdrant.query_points(
            collection_name=selected_collection,
            query=query_vector,
            query_filter=filters,
            limit=top_k,
            with_payload=True,
        )
        points = getattr(response, "points", response)
        return normalize_results("RAG", query, list(points))
    except ImportError as exc:
        return error_result("RAG_CLIENT_UNAVAILABLE", str(exc))
    except Exception as exc:
        return error_result(
            "RAG_SEARCH_FAILED",
            str(exc),
            {"collection": selected_collection},
        )


def _create_qdrant_client(url: str) -> QdrantSearchClient:
    from qdrant_client import QdrantClient

    return QdrantClient(url=url)
