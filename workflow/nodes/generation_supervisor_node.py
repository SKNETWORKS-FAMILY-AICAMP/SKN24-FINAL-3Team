# 산출물 생성 Supervisor를 실행하는 워크플로우 노드입니다.

from workflow.state import WorkflowState


def generation_supervisor_node(state: WorkflowState) -> WorkflowState:
    return state
