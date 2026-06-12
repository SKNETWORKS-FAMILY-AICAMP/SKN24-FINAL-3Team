# 아키텍처 설계서의 구조와 내용을 검증합니다.

from typing import Any

from agents.validation.schemas import duplicate_values, first_list, is_empty, make_check, missing_fields
from workflow.state import WorkflowState


TARGET = "architecture_analysis_agent"


def validate(state: WorkflowState) -> list[dict[str, Any]]:
    outputs = state.get("agent_outputs", {})
    output = outputs.get(TARGET, {})
    structure = output.get("architecture_structure_json")
    document = output.get("architecture_document_json")
    checks = [
        make_check("ARCH_OUTPUT_001", "아키텍처 출력 존재 검증", not is_empty(structure) and not is_empty(document), failure_type="ARCH_OUTPUT_MISSING", message="architecture_structure_json 또는 architecture_document_json이 없습니다.", target_agent=TARGET)
    ]
    if not isinstance(structure, dict) or not isinstance(document, dict):
        checks.append(make_check("ARCH_SCHEMA_001", "아키텍처 JSON Schema 검증", False, failure_type="ARCH_SCHEMA_ERROR", message="아키텍처 출력 구조가 올바르지 않습니다.", target_agent=TARGET))
        return checks + _mermaid_checks(outputs)

    source = {**document, **structure}
    missing = missing_fields(source, ["overview", "components", "relations", "layers", "deployment_environment"])
    components = first_list(source, "components")
    relations = first_list(source, "relations")
    checks.extend(
        [
            make_check("ARCH_SCHEMA_001", "아키텍처 필수 필드 검증", not missing, failure_type="ARCH_SCHEMA_ERROR", message="아키텍처 필수 필드가 누락되었습니다.", target_agent=TARGET, target_scope=missing),
            make_check("ARCH_COMPONENT_001", "컴포넌트 ID 중복 검증", not (duplicates := duplicate_values(components, "component_id", "id", "name")), failure_type="ARCH_COMPONENT_DUPLICATED", message="중복된 컴포넌트 ID가 있습니다.", target_agent=TARGET, target_scope=duplicates),
            make_check("ARCH_RELATION_001", "컴포넌트 관계 검증", bool(relations), failure_type="ARCH_RELATION_MISSING", message="컴포넌트 관계가 없습니다.", target_agent=TARGET),
        ]
    )
    config = state.get("etc", {}).get("architecture_config")
    checks.append(
        make_check("ARCH_CONFIG_001", "아키텍처 설정 반영 검증", config is None or bool(source.get("architecture_config_reflected") or source.get("architecture_config")), failure_type="ARCH_CONFIG_NOT_REFLECTED", message="architecture_config 반영 여부를 확인할 수 없습니다.", target_agent=TARGET)
    )
    return checks + _mermaid_checks(outputs)


def _mermaid_checks(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    output = outputs.get("mermaid_generation_agent", {})
    return [
        make_check("ARCH_MERMAID_001", "Mermaid 코드 존재 검증", not is_empty(output.get("mermaid_code")), failure_type="ARCH_MERMAID_CODE_MISSING", message="아키텍처 Mermaid 코드가 없습니다.", target_agent="mermaid_generation_agent"),
        make_check("ARCH_MERMAID_002", "Mermaid 이미지 렌더링 검증", not is_empty(output.get("mermaid_image_path")), failure_type="ARCH_MERMAID_RENDER_FAILED", message="아키텍처 Mermaid 이미지 렌더링 결과가 없습니다.", target_agent="mermaid_generation_agent"),
    ]
