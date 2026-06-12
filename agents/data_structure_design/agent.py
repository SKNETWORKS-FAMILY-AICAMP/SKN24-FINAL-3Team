# ERD 및 DB 데이터 구조 설계 Agent의 실행 진입점입니다.

from typing import Any

from workflow.state import WorkflowState


class DataStructureDesignAgent:
    def execute(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "status": "SUCCESS",
            "erd_entity_json": {},
            "erd_mermaid_json": {},
            "db_design_json": {},
            "warnings": [],
            "errors": [],
        }
