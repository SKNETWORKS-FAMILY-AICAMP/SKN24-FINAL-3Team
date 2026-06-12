# 요구사항 정의서의 구조와 내용을 검증합니다.

from typing import Any

from agents.validation.schemas import duplicate_values, is_empty, make_check, missing_fields
from workflow.state import WorkflowState


TARGET = "requirement_generation_agent"


def validate(state: WorkflowState) -> list[dict[str, Any]]:
    output = state.get("agent_outputs", {}).get(TARGET, {})
    requirements = output.get("final_requirement_json_list")
    items = requirements if isinstance(requirements, list) else []
    checks = [
        make_check(
            "SRS_OUTPUT_001",
            "요구사항 출력 존재 검증",
            bool(items),
            failure_type="SRS_OUTPUT_MISSING",
            message="final_requirement_json_list가 없거나 비어 있습니다.",
            target_agent=TARGET,
        )
    ]
    if not items:
        return checks

    invalid = [str(index) for index, item in enumerate(items) if not isinstance(item, dict)]
    checks.append(
        make_check(
            "SRS_SCHEMA_001",
            "요구사항 JSON Schema 검증",
            not invalid,
            failure_type="SRS_SCHEMA_ERROR",
            message="요구사항 목록에 객체가 아닌 항목이 있습니다.",
            target_agent=TARGET,
            target_scope=invalid,
        )
    )

    missing = []
    source_missing = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        req_id = str(item.get("req_id") or index)
        if missing_fields(item, ["req_id", "req_name", "requirement_type", "detail_text"]):
            missing.append(req_id)
        if is_empty(item.get("source_req_ids")) and is_empty(item.get("source_refs")):
            source_missing.append(req_id)
    checks.extend(
        [
            make_check(
                "SRS_FIELD_001",
                "필수 필드 검증",
                not missing,
                failure_type="SRS_REQUIRED_FIELD_MISSING",
                message="일부 요구사항에 필수 필드가 누락되었습니다.",
                target_agent=TARGET,
                target_scope=missing,
            ),
            make_check(
                "SRS_DUPLICATE_001",
                "요구사항 ID 중복 검증",
                not (duplicates := duplicate_values(items, "req_id")),
                failure_type="SRS_DUPLICATE_REQ_ID",
                message="중복된 req_id가 있습니다.",
                target_agent=TARGET,
                target_scope=duplicates,
            ),
            make_check(
                "SRS_DUPLICATE_002",
                "요구사항명 중복 검증",
                not (names := duplicate_values(items, "req_name")),
                failure_type="SRS_DUPLICATE_REQUIREMENT",
                message="중복된 요구사항명이 있습니다.",
                target_agent=TARGET,
                target_scope=names,
                severity="MEDIUM",
            ),
            make_check(
                "SRS_TRACE_001",
                "원본 요구사항 추적성 검증",
                not source_missing,
                failure_type="SRS_SOURCE_TRACE_MISSING",
                message="원본 RFP 요구사항을 추적할 source 정보가 누락되었습니다.",
                target_agent=TARGET,
                target_scope=source_missing,
            ),
        ]
    )

    types = {str(item.get("requirement_type", "")).lower() for item in items if isinstance(item, dict)}
    has_non_functional = any(
        value and value not in {"기능", "functional", "function"} for value in types
    )
    checks.append(
        make_check(
            "SRS_NFR_001",
            "비기능 요구사항 반영 검증",
            has_non_functional,
            failure_type="SRS_NON_FUNCTIONAL_MISSING",
            message="비기능 요구사항을 확인할 수 없습니다.",
            target_agent=TARGET,
            severity="MEDIUM",
            warning=True,
        )
    )
    return checks
