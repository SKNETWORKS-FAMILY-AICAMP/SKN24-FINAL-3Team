# Mermaid 코드 및 이미지 생성 Agent의 실행 진입점입니다.

from typing import Any

from workflow.state import WorkflowState


class MermaidGenerationAgent:
    def execute(self, state: WorkflowState) -> dict[str, Any]:
        return {
            "status": "SUCCESS",
            "mermaid_code": "",
            "mermaid_file_path": "",
            "mermaid_image_path": "",
            "warnings": [],
            "errors": [],
        }
