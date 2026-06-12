# 최종 문서 JSON을 기반으로 DOCX 파일을 생성하는 워크플로우 노드입니다.

from workflow.state import WorkflowState


def export_node(state: WorkflowState) -> WorkflowState:
    return state
