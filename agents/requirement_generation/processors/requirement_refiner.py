# 비기능 제약사항을 반영하여 요구사항을 정제합니다.

from copy import deepcopy
from typing import Any

from tools.llm.llm_client import LLMClient
from tools.llm.response_parser import parse_json_response
from tools.llm.send_api import send_parallel


def extract_constraints(search_results: list[dict[str, Any]]) -> list[str]:
    constraints: list[str] = []
    seen: set[str] = set()
    for result in search_results:
        text = str(result.get("content") or result.get("title") or "").strip()
        if text and text not in seen:
            constraints.append(text)
            seen.add(text)
    return constraints


def constraints_to_validation_criteria(constraints: list[str]) -> list[str]:
    return [f"{constraint.rstrip('.')} 준수 여부를 확인한다." for constraint in constraints]


def build_final_requirement(
    split_item: dict[str, Any],
    constraints: list[str],
) -> dict[str, Any]:
    item = deepcopy(split_item)
    requirement_id = str(item.get("requirement_id") or item.get("req_id") or "")
    requirement_name = str(item.get("requirement_name") or item.get("req_name") or "")
    description = str(
        item.get("description")
        or item.get("requirement_detail")
        or item.get("detail_text")
        or ""
    )
    source = _as_list(item.get("source") or item.get("source_req_ids") or [])
    existing_constraints = _as_list(item.get("constraints"))
    all_constraints = list(dict.fromkeys([*existing_constraints, *constraints]))
    existing_criteria = _as_list(item.get("validation_criteria"))
    criteria = list(
        dict.fromkeys(
            [
                *[str(value) for value in existing_criteria if value],
                *constraints_to_validation_criteria(all_constraints),
            ]
        )
    )
    return {
        "requirement_id": requirement_id,
        "requirement_name": requirement_name,
        "requirement_type": str(item.get("requirement_type") or "기능"),
        "description": description,
        "source": source,
        "constraints": all_constraints,
        "priority": item.get("priority") or "미지정",
        "validation_criteria": criteria,
        "note": item.get("note") or ("비기능 요구사항 RAG 검색 결과를 반영함" if constraints else ""),
    }


def normalize_task3_requirement(item: dict[str, Any]) -> dict[str, Any]:
    """Task3 GOLD 항목을 기존 SRS 산출물 계약 필드로 변환합니다."""

    requirement_id = str(
        item.get("requirement_id")
        or item.get("gold_id")
        or item.get("req_id")
        or ""
    )
    requirement_name = str(item.get("requirement_name") or item.get("req_name") or "")
    description = str(
        item.get("description")
        or item.get("requirement_detail")
        or item.get("detail_text")
        or ""
    )
    source = _as_list(item.get("source") or item.get("sources") or item.get("source_req_ids"))
    return {
        "requirement_id": requirement_id,
        "requirement_name": requirement_name,
        "requirement_type": str(item.get("requirement_type") or "기능"),
        "description": description,
        "source": source,
        "constraints": _as_list(item.get("constraints")),
        "priority": item.get("priority") or "미지정",
        "validation_criteria": _as_list(item.get("validation_criteria")),
        "note": item.get("note") or item.get("merge_basis") or "",
    }


def normalize_task3_output(value: Any) -> Any:
    """Task3 문서 래퍼 또는 항목 목록을 기존 SRS 요구사항 목록으로 변환합니다."""

    items = value.get("final_requirements") if isinstance(value, dict) else value
    if not isinstance(items, list):
        return value
    if not any(
        isinstance(item, dict)
        and (item.get("gold_id") or item.get("merge_basis") or item.get("source_task2_ids"))
        for item in items
    ):
        return items
    return [normalize_task3_requirement(item) for item in items if isinstance(item, dict)]


def enrich_gold_requirements_parallel(
    gold_items: list[dict[str, Any]],
    rag_results_by_item: list[list[dict[str, Any]]],
    *,
    llm_client: LLMClient | None = None,
    max_workers: int = 4,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """GOLD 결과를 표준 SRS 필드로 변환하고 빈 보강 컬럼만 RAG로 채웁니다."""

    warnings: list[dict[str, Any]] = []
    fallback_items = [
        _merge_supplement(normalize_task3_requirement(item), _supplement_from_rag(results))
        for item, results in zip(gold_items, rag_results_by_item, strict=False)
    ]
    if llm_client is None or not gold_items:
        return fallback_items, warnings

    requests = [
        {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON with only supplemental SRS columns based on RAG evidence. "
                        "Do not rewrite requirement_id, requirement_name, requirement_type, "
                        "description, source, or note. Allowed keys: constraints, priority, "
                        "validation_criteria, rag_validation."
                    ),
                },
                {
                    "role": "user",
                    "content": str(
                        {
                            "requirement": normalize_task3_requirement(item),
                            "rag_results": rag_results,
                            "fallback_supplement": _supplement_from_rag(rag_results),
                        }
                    ),
                },
            ]
        }
        for item, rag_results in zip(gold_items, rag_results_by_item, strict=False)
    ]
    result = send_parallel(requests, client=llm_client, max_workers=max_workers)
    if not result["success"]:
        warnings.append({"code": "REQUIREMENT_RAG_SUPPLEMENT_LLM_FAILED", "message": result["error"]["message"]})
        return fallback_items, warnings

    enriched: list[dict[str, Any]] = []
    for index, item_result in enumerate(result["data"]):
        supplement = _supplement_from_rag(rag_results_by_item[index])
        if item_result and item_result["success"]:
            parsed = parse_json_response(item_result["data"])
            if parsed["success"] and isinstance(parsed["data"], dict):
                supplement = _normalize_supplement(parsed["data"], supplement)
        enriched.append(_merge_supplement(normalize_task3_requirement(gold_items[index]), supplement))
    return enriched, warnings


def refine_requirements_parallel(
    split_items: list[dict[str, Any]],
    rag_results_by_item: list[list[dict[str, Any]]],
    *,
    llm_client: LLMClient | None = None,
    max_workers: int = 4,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """split item과 RAG 결과를 LLM3로 병렬 정제합니다."""

    warnings: list[dict[str, Any]] = []
    fallback_items = [
        build_final_requirement(item, extract_constraints(results))
        for item, results in zip(split_items, rag_results_by_item, strict=False)
    ]
    if llm_client is None or not split_items:
        return fallback_items, warnings

    requests = [
        {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "기능 요구사항과 RAG 검색 결과를 기준으로 최종 요구사항 JSON을 생성하세요. "
                        "description은 기능 내용을 유지하고, 보안/성능/품질/인터페이스/데이터 제약은 "
                        "constraints와 validation_criteria에 검증 가능한 문장으로 정리하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": str(
                        {
                            "split_requirement": split_item,
                            "rag_results": rag_results,
                            "fallback_output": fallback,
                        }
                    ),
                },
            ]
        }
        for split_item, rag_results, fallback in zip(split_items, rag_results_by_item, fallback_items, strict=False)
    ]
    result = send_parallel(requests, client=llm_client, max_workers=max_workers)
    if not result["success"]:
        warnings.append({"code": "REQUIREMENT_REFINE_LLM_FAILED", "message": result["error"]["message"]})
        return fallback_items, warnings

    refined: list[dict[str, Any]] = []
    for index, item_result in enumerate(result["data"]):
        if not item_result or not item_result["success"]:
            refined.append(fallback_items[index])
            continue
        parsed = parse_json_response(item_result["data"])
        value = parsed["data"] if parsed["success"] else None
        refined.append(
            _normalize_final_requirement(value, fallback_items[index])
            if isinstance(value, dict)
            else fallback_items[index]
        )
    return refined, warnings


def _supplement_from_rag(search_results: list[dict[str, Any]]) -> dict[str, Any]:
    constraints = extract_constraints(search_results)
    return {
        "constraints": constraints,
        "priority": "미지정",
        "validation_criteria": constraints_to_validation_criteria(constraints),
        "rag_validation": {
            "status": "APPLIED" if constraints else "NO_EVIDENCE",
            "evidence": search_results,
            "notes": "RAG evidence applied to supplemental SRS columns." if constraints else "No RAG evidence found.",
        },
    }


def _normalize_supplement(raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    constraints = _as_list(raw.get("constraints", fallback.get("constraints", [])))
    validation_criteria = _as_list(raw.get("validation_criteria", fallback.get("validation_criteria", [])))
    rag_validation = raw.get("rag_validation", fallback.get("rag_validation", {}))
    if not isinstance(rag_validation, dict):
        rag_validation = fallback.get("rag_validation", {})
    return {
        "constraints": constraints,
        "priority": raw.get("priority") or fallback.get("priority") or "미지정",
        "validation_criteria": validation_criteria,
        "rag_validation": rag_validation,
    }


def _merge_supplement(item: dict[str, Any], supplement: dict[str, Any]) -> dict[str, Any]:
    merged = dict(item)
    for key in ("constraints", "validation_criteria"):
        if not merged.get(key):
            merged[key] = supplement.get(key, [])
    if merged.get("priority") in (None, "", "미지정"):
        merged["priority"] = supplement.get("priority") or "미지정"
    return merged


def _normalize_final_requirement(item: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    if item.get("gold_id") or item.get("sources") or item.get("merge_basis"):
        return normalize_task3_requirement(item)

    merged = {**fallback, **item}
    source = _as_list(merged.get("source") or merged.get("source_req_ids") or fallback.get("source", []))
    constraints = _as_list(merged.get("constraints"))
    validation_criteria = _as_list(merged.get("validation_criteria")) or constraints_to_validation_criteria(constraints)
    return {
        "requirement_id": str(merged.get("requirement_id") or merged.get("req_id") or fallback["requirement_id"]),
        "requirement_name": str(merged.get("requirement_name") or merged.get("req_name") or fallback["requirement_name"]),
        "requirement_type": str(merged.get("requirement_type") or fallback.get("requirement_type") or "기능"),
        "description": str(merged.get("description") or merged.get("detail_text") or fallback["description"]),
        "source": source,
        "constraints": constraints,
        "priority": merged.get("priority") or "미지정",
        "validation_criteria": validation_criteria,
        "note": merged.get("note") or fallback.get("note") or "",
    }


def _as_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]
