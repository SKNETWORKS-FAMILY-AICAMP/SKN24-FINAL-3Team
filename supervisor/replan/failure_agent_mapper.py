# 실패 유형별로 재실행할 Agent를 매핑합니다.

FAILURE_AGENT_MAP: dict[str, list[str]] = {
    "DOCUMENT_MERGE_OUTPUT_MISSING": ["document_merge_agent"],
    "SRS_SCHEMA_ERROR": ["requirement_generation_agent"],
    "SRS_MEETING_CHANGE_MISSING": [
        "document_merge_agent",
        "requirement_generation_agent",
    ],
    "INTERFACE_IMAGE_MAPPING_MISSING": ["image_analysis_agent"],
    "INTERFACE_IMAGE_UPDATE_MESSAGE_MISSING": ["image_analysis_agent"],
    "TS_STEP_DETAIL_MISSING": ["test_scenario_generation_agent"],
    "TS_INTERFACE_MAPPING_MISSING": [
        "document_merge_agent",
        "test_scenario_generation_agent",
    ],
    "ERD_PK_MISSING": ["data_structure_design_agent"],
    "ERD_FK_INVALID": ["data_structure_design_agent"],
    "ERD_MERMAID_RENDER_FAILED": ["mermaid_generation_agent"],
    "DB_COLUMN_MISSING": ["data_structure_design_agent"],
    "DB_CONSTRAINT_INVALID": ["data_structure_design_agent"],
    "ARCH_CONFIG_NOT_REFLECTED": ["architecture_analysis_agent"],
    "ARCH_COMPONENT_MISSING": ["architecture_analysis_agent"],
    "ARCH_MERMAID_RENDER_FAILED": ["mermaid_generation_agent"],
}


def get_failure_agents(failure_type: str) -> list[str]:
    return list(FAILURE_AGENT_MAP.get(failure_type, []))
