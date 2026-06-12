# 워크플로우 실행 중 생성된 임시 파일을 정리하는 노드입니다.

from workflow.state import WorkflowState


def cleanup_node(state: WorkflowState) -> WorkflowState:
    return state
