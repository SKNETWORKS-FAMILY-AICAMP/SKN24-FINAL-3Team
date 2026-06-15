# 요구사항 생성 Agent의 실행 진입점입니다.

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from agents.requirement_generation.processors import (
    build_integrated_text,
    build_rag_queries_parallel,
    filter_function_requirements,
    refine_requirements_parallel,
    split_function_requirements,
)
from tools.llm.llm_client import LLMClient
from tools.result import ToolResult
from tools.search.search_router import search
from workflow.state import WorkflowState


class RequirementGenerationAgent:
    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        search_tool: Callable[..., ToolResult] = search,
        max_parallel_workers: int = 4,
    ) -> None:
        self.llm_client = llm_client
        self.search_tool = search_tool
        self.max_parallel_workers = max_parallel_workers

    def execute(self, state: WorkflowState) -> dict[str, Any]:
        if str(state.get("docs_cd", "")).upper() != "SRS" or str(state.get("udt_yn", "")).upper() != "N":
            output = self._failed("REQUIREMENT_GENERATION_INVALID_MODE", "requirement_generation_agent는 SRS 신규 생성에서만 실행할 수 있습니다.")
            return self._store(state, output)

        integrated = state.get("agent_outputs", {}).get("document_merge_agent", {}).get(
            "integrated_requirement_json_list"
        )
        if not isinstance(integrated, list) or not integrated:
            return self._store(state, self._failed("INTEGRATED_REQUIREMENT_MISSING", "integrated_requirement_json_list가 없거나 비어 있습니다."))

        functional = filter_function_requirements(integrated)
        if not functional:
            return self._store(state, self._failed("FUNCTION_REQUIREMENT_MISSING", "기능 요구사항이 없습니다."))
        non_functional_context = _non_functional_context(integrated)

        integrated_text = build_integrated_text(functional)
        split_items, warnings = split_function_requirements(
            functional,
            integrated_text,
            llm_client=self.llm_client,
        )
        queries, query_warnings = build_rag_queries_parallel(
            split_items,
            llm_client=self.llm_client,
            max_workers=self.max_parallel_workers,
        )
        warnings.extend(query_warnings)
        rag_results_by_item, rag_warnings, search_debug = self._search_rag_parallel(
            split_items,
            queries,
            state,
            non_functional_context,
        )
        warnings.extend(rag_warnings)
        final_items, refine_warnings = refine_requirements_parallel(
            split_items,
            rag_results_by_item,
            llm_client=self.llm_client,
            max_workers=self.max_parallel_workers,
        )
        warnings.extend(refine_warnings)

        output: dict[str, Any] = {
            "status": "SUCCESS",
            "final_requirement_json_list": final_items,
            "warnings": warnings,
            "errors": [],
        }
        if bool(state.get("etc", {}).get("debug")):
            output["debug"] = {
                "functional_requirement_list": functional,
                "non_functional_context": non_functional_context,
                "integrated_function_text": integrated_text,
                "split_function_requirement_list": split_items,
                "rag_searches": search_debug,
            }
        return self._store(state, output)

    def _search_rag_parallel(
        self,
        split_items: list[dict[str, Any]],
        queries: list[str],
        state: WorkflowState,
        non_functional_context: list[dict[str, Any]],
    ) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
        warnings: list[dict[str, Any]] = []
        results: list[list[dict[str, Any]]] = [[] for _ in split_items]
        debug: list[dict[str, Any]] = [{} for _ in split_items]

        def invoke(index: int) -> tuple[int, ToolResult, dict[str, Any], str]:
            split_item = split_items[index]
            query = queries[index]
            filters = {
                "project_sn": state.get("project_sn"),
                "requirement_source_id": split_item.get("source", []),
                "rfp_id": split_item.get("rfp_id"),
                "requirement_type": ["보안", "성능", "품질", "인터페이스", "데이터"],
            }
            return (
                index,
                self.search_tool(query, search_targets="RAG", filters=filters),
                filters,
                query,
            )

        with ThreadPoolExecutor(max_workers=self.max_parallel_workers) as executor:
            futures = {executor.submit(invoke, index): index for index in range(len(split_items))}
            for future in as_completed(futures):
                index, search_result, filters, query = future.result()
                normalized_results = (
                    search_result["data"]["normalized_results"]
                    if search_result["success"]
                    else []
                )
                normalized_results = _dedupe_relevant_results(normalized_results)
                if not normalized_results:
                    normalized_results = _non_functional_fallback_results(non_functional_context)
                results[index] = normalized_results
                debug[index] = {
                    "query": query,
                    "filters": filters,
                    "normalized_results": normalized_results,
                }
                if not search_result["success"]:
                    warnings.append(
                        {
                            "code": "REQUIREMENT_RAG_SEARCH_FAILED",
                            "message": search_result["error"]["message"],
                            "query": query,
                        }
                    )
        return results, warnings, debug

    @staticmethod
    def _store(state: WorkflowState, output: dict[str, Any]) -> dict[str, Any]:
        state.setdefault("agent_outputs", {})["requirement_generation_agent"] = output
        return output

    @staticmethod
    def _failed(code: str, message: str) -> dict[str, Any]:
        return {
            "status": "FAILED",
            "failure_type": code,
            "warnings": [],
            "errors": [{"code": code, "message": message}],
        }


def _dedupe_relevant_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in sorted(results, key=lambda item: item.get("score") or 0, reverse=True):
        score = result.get("score")
        if isinstance(score, (int, float)) and score < 0.2:
            continue
        key = str(result.get("citation") or result.get("content") or result.get("title") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _non_functional_context(items: list[Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if isinstance(item, dict)
        and not _is_functional_type(item.get("requirement_type") or item.get("type"))
    ]


def _non_functional_fallback_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for item in items:
        content = _constraint_text(item)
        if not content:
            continue
        results.append(
            {
                "source_kind": "RAG",
                "source": "RAG",
                "title": str(item.get("req_name") or item.get("requirement_name") or ""),
                "content": content,
                "score": 0.5,
                "metadata": {
                    "requirement_id": item.get("req_id") or item.get("requirement_id"),
                    "requirement_type": item.get("requirement_type") or item.get("type"),
                    "source": "document_merge_agent",
                },
                "citation": str(item.get("req_id") or item.get("requirement_id") or ""),
            }
        )
    return _dedupe_relevant_results(results)


def _constraint_text(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("req_name") or item.get("requirement_name") or "").strip(),
        str(item.get("detail_text") or item.get("description") or item.get("content") or "").strip(),
        _join_values(item.get("constraints")),
        _join_values(item.get("validation_criteria")),
    ]
    return " - ".join(part for part in parts if part)


def _join_values(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if str(item).strip())
    if isinstance(value, dict):
        return " ".join(str(item) for item in value.values() if str(item).strip())
    return str(value or "").strip()


def _is_functional_type(value: Any) -> bool:
    requirement_type = str(value or "").strip().lower()
    return requirement_type.startswith("기능") or requirement_type.startswith("functional") or requirement_type == "function"
