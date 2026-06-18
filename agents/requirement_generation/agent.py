from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Protocol

from agents.requirement_generation.processors import (
    build_rag_queries_parallel,
    enrich_gold_requirements_parallel,
    filter_function_requirements,
)
from tools.llm.llm_client import LLMClient
from tools.result import ToolResult
from tools.search.search_router import search
from workflow.state import WorkflowState


class GoldRequirementService(Protocol):
    def generate_from_dict(
        self,
        document: dict[str, Any],
        *,
        output_dir: Path | str | None = None,
        job_id: str | None = None,
        replace_existing: bool = True,
    ) -> dict[str, Any]: ...


class RequirementGenerationAgent:
    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        search_tool: Callable[..., ToolResult] = search,
        gold_service: GoldRequirementService | None = None,
        max_parallel_workers: int = 4,
    ) -> None:
        self.llm_client = llm_client
        self.search_tool = search_tool
        self.gold_service = gold_service
        self.max_parallel_workers = max_parallel_workers

    def execute(self, state: WorkflowState) -> dict[str, Any]:
        if str(state.get("docs_cd", "")).upper() != "SRS" or str(state.get("udt_yn", "")).upper() != "N":
            output = self._failed(
                "REQUIREMENT_GENERATION_INVALID_MODE",
                "requirement_generation_agent only supports SRS create mode.",
            )
            return self._store(state, output)

        integrated = state.get("agent_outputs", {}).get("document_merge_agent", {}).get(
            "integrated_requirement_json_list"
        )
        if not isinstance(integrated, list) or not integrated:
            return self._store(
                state,
                self._failed(
                    "INTEGRATED_REQUIREMENT_MISSING",
                    "document_merge_agent.integrated_requirement_json_list is required.",
                ),
            )

        functional = filter_function_requirements(integrated)
        if not functional:
            return self._store(
                state,
                self._failed("FUNCTION_REQUIREMENT_MISSING", "No functional requirements found."),
            )
        non_functional_context = _non_functional_context(integrated)

        warnings: list[dict[str, Any]] = []
        gold_input = _build_gold_input(state, functional, non_functional_context)
        try:
            gold_output = self._generate_gold_requirements(gold_input, state)
        except Exception as exc:
            return self._store(
                state,
                self._failed("REQUIREMENT_GOLD_GENERATION_FAILED", str(exc)),
            )

        gold_items = _extract_gold_items(gold_output)
        if not gold_items:
            return self._store(
                state,
                self._failed("REQUIREMENT_GOLD_EMPTY", "GOLD final_requirements is empty."),
            )

        queries, query_warnings = build_rag_queries_parallel(
            gold_items,
            llm_client=self.llm_client,
            max_workers=self.max_parallel_workers,
        )
        warnings.extend(query_warnings)

        rag_results_by_item, rag_warnings, search_debug = self._search_rag_parallel(
            gold_items,
            queries,
            state,
            non_functional_context,
        )
        warnings.extend(rag_warnings)

        final_items, supplement_warnings = enrich_gold_requirements_parallel(
            gold_items,
            rag_results_by_item,
            llm_client=self.llm_client,
            max_workers=self.max_parallel_workers,
        )
        warnings.extend(supplement_warnings)

        output: dict[str, Any] = {
            "status": "SUCCESS",
            "final_requirement_json_list": final_items,
            "gold_generation_result": gold_output,
            "warnings": warnings,
            "errors": [],
        }
        if bool(state.get("etc", {}).get("debug")):
            output["debug"] = {
                "functional_requirement_list": functional,
                "non_functional_context": non_functional_context,
                "gold_generation_input": gold_input,
                "gold_final_requirement_list": gold_items,
                "rag_searches": search_debug,
            }
        return self._store(state, output)

    def _generate_gold_requirements(
        self,
        gold_input: dict[str, Any],
        state: WorkflowState,
    ) -> dict[str, Any]:
        service = self.gold_service
        if service is None:
            from agents.fine_tuning_agent.requirements_gold_agent import (
                RequirementsGenerationService,
            )

            service = RequirementsGenerationService.get_instance()

        output_dir = state.get("etc", {}).get("requirement_gold_output_dir")
        job_id = state.get("etc", {}).get("requirement_gold_job_id") or gold_input["document_id"]
        return service.generate_from_dict(
            gold_input,
            output_dir=output_dir,
            job_id=str(job_id),
            replace_existing=True,
        )

    def _search_rag_parallel(
        self,
        gold_items: list[dict[str, Any]],
        queries: list[str],
        state: WorkflowState,
        non_functional_context: list[dict[str, Any]],
    ) -> tuple[list[list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
        warnings: list[dict[str, Any]] = []
        results: list[list[dict[str, Any]]] = [[] for _ in gold_items]
        debug: list[dict[str, Any]] = [{} for _ in gold_items]

        def invoke(index: int) -> tuple[int, ToolResult, dict[str, Any], str]:
            gold_item = gold_items[index]
            query = queries[index]
            filters = {
                "project_sn": state.get("project_sn"),
                "requirement_source_id": gold_item.get("sources") or gold_item.get("source") or [],
                "rfp_id": gold_item.get("rfp_id"),
                "requirement_type": ["보안", "성능", "품질", "인터페이스", "데이터"],
            }
            return (
                index,
                self.search_tool(query, search_targets="RAG", filters=filters),
                filters,
                query,
            )

        with ThreadPoolExecutor(max_workers=self.max_parallel_workers) as executor:
            futures = {executor.submit(invoke, index): index for index in range(len(gold_items))}
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


def _build_gold_input(
    state: WorkflowState,
    functional: list[dict[str, Any]],
    non_functional_context: list[dict[str, Any]],
) -> dict[str, Any]:
    document_id = _document_id(state)
    return {
        "document_id": document_id,
        "document_name": _document_name(state, document_id),
        "functional_requirements": [
            _normalize_gold_functional_requirement(item, index)
            for index, item in enumerate(functional, start=1)
        ],
        "scope_reference_requirements": [
            _normalize_scope_requirement(item, index)
            for index, item in enumerate(non_functional_context, start=1)
            if _description(item)
        ],
    }


def _normalize_gold_functional_requirement(item: dict[str, Any], index: int) -> dict[str, Any]:
    requirement_id = _source_id(item)
    if requirement_id == "UNKNOWN":
        requirement_id = f"FUR-{index:03d}"
    return {
        "requirement_id": requirement_id,
        "requirement_name": _name(item) or requirement_id,
        "requirement_type": str(item.get("requirement_type") or item.get("type") or "기능"),
        "requirement_definition": str(item.get("requirement_definition") or item.get("definition") or ""),
        "requirement_detail": _description(item),
        "source": item.get("source") or item.get("source_req_ids") or item.get("source_location") or requirement_id,
        "source_location": item.get("source_location"),
    }


def _normalize_scope_requirement(item: dict[str, Any], index: int) -> dict[str, Any]:
    scope_id = _source_id(item)
    if scope_id == "UNKNOWN":
        scope_id = f"SCOPE-{index:03d}"
    return {
        "scope_id": scope_id,
        "requirement_name": _name(item) or scope_id,
        "requirement_detail": _description(item),
        "global_scope": True,
    }


def _extract_gold_items(gold_output: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("final_requirements", "gold_requirement_specification", "final_requirement_json_list"):
        value = gold_output.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _document_id(state: WorkflowState) -> str:
    for key in ("document_id", "docs_id"):
        value = state.get(key)  # type: ignore[literal-required]
        if value:
            return str(value)
    base_path = state.get("base_rfp_path")
    if base_path:
        return Path(str(base_path)).stem
    project_sn = state.get("project_sn")
    return f"DOC-{project_sn}" if project_sn is not None else "DOC-SRS"


def _document_name(state: WorkflowState, document_id: str) -> str:
    for key in ("document_name", "docs_name"):
        value = state.get(key)  # type: ignore[literal-required]
        if value:
            return str(value)
    base_path = state.get("base_rfp_path")
    return Path(str(base_path)).name if base_path else document_id


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
                "title": _name(item),
                "content": content,
                "score": 0.5,
                "metadata": {
                    "requirement_id": item.get("req_id") or item.get("requirement_id"),
                    "requirement_type": item.get("requirement_type") or item.get("type"),
                    "source": "document_merge_agent",
                },
                "citation": _source_id(item),
            }
        )
    return _dedupe_relevant_results(results)


def _constraint_text(item: dict[str, Any]) -> str:
    parts = [
        _name(item),
        _description(item),
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


def _source_id(item: dict[str, Any]) -> str:
    return str(item.get("req_id") or item.get("requirement_id") or item.get("id") or "UNKNOWN")


def _name(item: dict[str, Any]) -> str:
    return str(item.get("req_name") or item.get("requirement_name") or item.get("name") or "")


def _description(item: dict[str, Any]) -> str:
    return str(
        item.get("requirement_detail")
        or item.get("detail_text")
        or item.get("description")
        or item.get("content")
        or ""
    )


def _is_functional_type(value: Any) -> bool:
    requirement_type = str(value or "").strip().lower()
    return (
        requirement_type.startswith("기능")
        or requirement_type.startswith("functional")
        or requirement_type == "function"
        or requirement_type.startswith("湲곕뒫")
    )
