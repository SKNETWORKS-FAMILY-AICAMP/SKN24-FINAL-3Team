# 인터페이스 설계서의 구조와 내용을 검증합니다.

from typing import Any

from agents.validation.schemas import duplicate_values, is_empty, make_check, missing_fields
from workflow.state import WorkflowState


TARGET = "image_analysis_agent"
MATCH_STATUSES = {
    "MATCHED",
    "IMAGE_MODIFY_REQUIRED",
    "IMAGE_ADD_REQUIRED",
    "IMAGE_DELETE_CANDIDATE",
    "UNMAPPED_IMAGE",
}


def validate(state: WorkflowState) -> list[dict[str, Any]]:
    items = state.get("agent_outputs", {}).get(TARGET, {}).get(
        "interface_image_analysis_json_list"
    )
    screens = items if isinstance(items, list) else []
    checks = [
        make_check(
            "INTERFACE_OUTPUT_001",
            "인터페이스 출력 존재 검증",
            bool(screens),
            failure_type="INTERFACE_OUTPUT_MISSING",
            message="interface_image_analysis_json_list가 없거나 비어 있습니다.",
            target_agent=TARGET,
        )
    ]
    if not screens:
        return checks

    invalid, missing, mapping_missing, image_missing, status_invalid = [], [], [], [], []
    for index, screen in enumerate(screens):
        scope = str(screen.get("screen_id") or index) if isinstance(screen, dict) else str(index)
        if not isinstance(screen, dict):
            invalid.append(scope)
            continue
        if missing_fields(screen, ["screen_id", "screen_name", "description", "match_status"]):
            missing.append(scope)
        if is_empty(screen.get("matched_requirement_ids")):
            mapping_missing.append(scope)
        if is_empty(screen.get("image_path")) and is_empty(screen.get("image_status")):
            image_missing.append(scope)
        if screen.get("match_status") not in MATCH_STATUSES:
            status_invalid.append(scope)
    checks.extend(
        [
            make_check("INTERFACE_SCHEMA_001", "화면 JSON Schema 검증", not invalid, failure_type="INTERFACE_SCHEMA_ERROR", message="화면 목록에 객체가 아닌 항목이 있습니다.", target_agent=TARGET, target_scope=invalid),
            make_check("INTERFACE_FIELD_001", "화면 필수 필드 검증", not missing, failure_type="INTERFACE_DESCRIPTION_MISSING", message="화면 필수 필드가 누락되었습니다.", target_agent=TARGET, target_scope=missing),
            make_check("INTERFACE_ID_001", "화면 ID 중복 검증", not (duplicates := duplicate_values(screens, "screen_id")), failure_type="INTERFACE_SCREEN_ID_DUPLICATED", message="중복된 screen_id가 있습니다.", target_agent=TARGET, target_scope=duplicates),
            make_check("INTERFACE_REQ_001", "요구사항 화면 매핑 검증", not mapping_missing, failure_type="INTERFACE_REQUIREMENT_MAPPING_MISSING", message="요구사항과 매핑되지 않은 화면이 있습니다.", target_agent=TARGET, target_scope=mapping_missing),
            make_check("INTERFACE_IMAGE_001", "이미지 매핑 검증", not image_missing, failure_type="INTERFACE_IMAGE_MAPPING_MISSING", message="이미지 경로 또는 이미지 상태가 누락되었습니다.", target_agent=TARGET, target_scope=image_missing),
            make_check("INTERFACE_IMAGE_002", "이미지 상태 검증", not status_invalid, failure_type="INTERFACE_IMAGE_STATUS_INVALID", message="허용되지 않은 match_status가 있습니다.", target_agent=TARGET, target_scope=status_invalid),
        ]
    )
    return checks
