# 비기능 요구사항 검색에 사용할 RAG 질의를 생성합니다.

from typing import Any

from tools.llm.llm_client import LLMClient
from tools.llm.response_parser import parse_json_response
from tools.llm.send_api import send_parallel


NON_FUNCTIONAL_CATEGORIES = ["보안", "성능", "품질", "인터페이스", "데이터"]


def build_rag_query(item: dict[str, Any]) -> str:
    name = item.get("requirement_name") or item.get("req_name") or ""
    description = (
        item.get("requirement_detail")
        or item.get("description")
        or item.get("detail_text")
        or ""
    )
    categories = ", ".join(NON_FUNCTIONAL_CATEGORIES)
    return f"{name} {description} 관련 {categories} 정책 표준 제약사항"


def build_rag_queries_parallel(
    items: list[dict[str, Any]],
    *,
    llm_client: LLMClient | None = None,
    max_workers: int = 4,
) -> tuple[list[str], list[dict[str, Any]]]:
    """split item별 비기능 RAG query를 병렬 생성합니다."""

    warnings: list[dict[str, Any]] = []
    fallback = [build_rag_query(item) for item in items]
    if llm_client is None or not items:
        return fallback, warnings

    requests = [
        {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "기능 요구사항에 연관된 보안, 성능, 품질, 인터페이스, 데이터 "
                        "비기능 요구사항 검색용 RAG query를 JSON으로 반환하세요. "
                        "형식: {\"query\": \"...\"}"
                    ),
                },
                {"role": "user", "content": str(item)},
            ]
        }
        for item in items
    ]
    result = send_parallel(requests, client=llm_client, max_workers=max_workers)
    if not result["success"]:
        warnings.append({"code": "REQUIREMENT_QUERY_BUILDER_FAILED", "message": result["error"]["message"]})
        return fallback, warnings

    queries: list[str] = []
    for index, item_result in enumerate(result["data"]):
        query = ""
        if item_result and item_result["success"]:
            parsed = parse_json_response(item_result["data"])
            if parsed["success"]:
                value = parsed["data"]
                if isinstance(value, dict):
                    query = str(value.get("query") or "").strip()
                elif isinstance(value, str):
                    query = value.strip()
        queries.append(query or fallback[index])
    return queries, warnings
