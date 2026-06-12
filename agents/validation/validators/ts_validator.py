# 통합시험 시나리오의 구조와 내용을 검증합니다.

from typing import Any

from agents.validation.schemas import duplicate_values, first_list, is_empty, make_check
from workflow.state import WorkflowState


TARGET = "test_scenario_generation_agent"


def validate(state: WorkflowState) -> list[dict[str, Any]]:
    document = state.get("agent_outputs", {}).get(TARGET, {}).get(
        "integrated_test_scenario_json"
    )
    checks = [
        make_check("TS_OUTPUT_001", "시험 시나리오 출력 존재 검증", isinstance(document, dict) and bool(document), failure_type="TS_OUTPUT_MISSING", message="integrated_test_scenario_json이 없거나 비어 있습니다.", target_agent=TARGET)
    ]
    if not isinstance(document, dict) or not document:
        return checks

    scenarios = first_list(document, "scenario_json_list", "scenarios")
    cases = first_list(document, "test_case_json_list", "test_cases")
    steps = first_list(document, "step_json_list", "steps")
    checks.append(
        make_check("TS_SCHEMA_001", "시험 시나리오 필수 구조 검증", bool(scenarios) and bool(cases) and bool(steps), failure_type="TS_SCHEMA_ERROR", message="scenario_json_list, test_case_json_list, step_json_list가 필요합니다.", target_agent=TARGET)
    )
    checks.extend(
        [
            make_check("TS_SCENARIO_001", "시나리오 ID 중복 검증", not (scenario_duplicates := duplicate_values(scenarios, "scenario_id", "id")), failure_type="TS_SCENARIO_ID_DUPLICATED", message="중복된 시나리오 ID가 있습니다.", target_agent=TARGET, target_scope=scenario_duplicates),
            make_check("TS_CASE_001", "시험케이스 ID 중복 검증", not (case_duplicates := duplicate_values(cases, "test_case_id", "case_id", "id")), failure_type="TS_TEST_CASE_ID_DUPLICATED", message="중복된 시험케이스 ID가 있습니다.", target_agent=TARGET, target_scope=case_duplicates),
        ]
    )
    missing_detail = []
    required_aliases = [
        ("처리내용", "process", "action"),
        ("시험항목", "test_item"),
        ("사전조건", "precondition"),
        ("입력값", "input", "input_value"),
        ("예상결과", "expected_result"),
        ("화면ID", "screen_id"),
    ]
    for index, step in enumerate(steps):
        scope = str(step.get("step_id") or step.get("step_no") or index) if isinstance(step, dict) else str(index)
        if not isinstance(step, dict) or any(
            all(is_empty(step.get(alias)) for alias in aliases) for aliases in required_aliases
        ):
            missing_detail.append(scope)
    checks.append(
        make_check("TS_STEP_001", "Step 상세 정보 누락 검증", not missing_detail, failure_type="TS_STEP_DETAIL_MISSING", message="일부 Step에 필수 상세 정보가 누락되었습니다.", target_agent=TARGET, target_scope=missing_detail)
    )
    return checks
