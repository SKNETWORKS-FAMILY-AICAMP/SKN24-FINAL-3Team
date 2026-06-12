# 요청 검증, 데이터 조회, 파일 다운로드 및 워크플로우 상태 초기화를 수행합니다.

from workflow.state import WorkflowState


def request_preprocess_node(state: WorkflowState) -> WorkflowState:
    return state
