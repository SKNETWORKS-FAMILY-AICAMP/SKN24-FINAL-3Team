# 시험 절차, 입력값 및 예상 결과를 생성하고 정제합니다.

from typing import Any

from tools.llm.llm_client import LLMClient
from tools.llm.response_parser import parse_json_response
from tools.llm.send_api import send_parallel


def generate_steps(
    test_cases: list[dict[str, Any]],
    interfaces: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    steps = _fallback_steps(test_cases, interfaces)
    return steps, []


def generate_steps_with_llm(
    test_cases: list[dict[str, Any]],
    interfaces: list[dict[str, Any]],
    *,
    llm_client: LLMClient | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if llm_client is None:
        return generate_steps(test_cases, interfaces)

    skeletons, skeleton_warnings = _generate_step_skeletons(test_cases, llm_client)
    detailed, detail_warnings = _generate_step_details(skeletons, test_cases, interfaces, llm_client)
    return detailed, [*skeleton_warnings, *detail_warnings]


def refine_steps(
    steps: list[dict[str, Any]],
    *,
    llm_client: LLMClient | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fallback = [_normalize_step(step, index, None, []) for index, step in enumerate(steps, start=1)]
    if llm_client is None:
        return fallback, []

    result = send_parallel(
        [
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Step별 상세 정보를 검토하고 정제하세요. 시험항목, 사전조건, 입력값, 예상결과, "
                            "화면ID 누락 여부를 확인하고 JSON으로 step을 반환하세요."
                        ),
                    },
                    {"role": "user", "content": str(step)},
                ]
            }
            for step in steps
        ],
        client=llm_client,
    )
    warnings: list[dict[str, Any]] = []
    if not result["success"]:
        return fallback, [{"code": "TS_STEP_REVIEW_LLM_FAILED", "message": result["error"]["message"]}]

    refined: list[dict[str, Any]] = []
    for index, (step, response) in enumerate(zip(steps, result["data"]), start=1):
        parsed = _parse_step(response)
        if parsed is None:
            warnings.append(
                {
                    "code": "TS_STEP_REVIEW_FALLBACK",
                    "message": f"Step {index} 상세 검토 결과를 기본값으로 대체했습니다.",
                }
            )
            parsed = step
        refined.append(_normalize_step(parsed, index, None, []))
    return refined, warnings


def build_step_detail_list(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details = []
    for index, step in enumerate(steps, start=1):
        details.append(
            {
                "step_detail_id": str(step.get("step_detail_id") or f"STEP-DTL-{index:04d}"),
                "step_id": str(step.get("step_id") or f"STEP-{index:04d}"),
                "test_case_id": str(step.get("test_case_id") or ""),
                "step_no": step.get("step_no") or index,
                "처리내용": step.get("처리내용") or step.get("process") or step.get("action") or "",
                "시험항목": step.get("시험항목") or step.get("test_item") or "",
                "사전조건": step.get("사전조건") or step.get("precondition") or "",
                "입력값": step.get("입력값") or step.get("input") or step.get("input_value") or "",
                "예상결과": step.get("예상결과") or step.get("expected_result") or "",
                "화면ID": step.get("화면ID") or step.get("screen_id") or "",
                "screen_id": step.get("screen_id") or step.get("화면ID") or "",
            }
        )
    return details


def _fallback_steps(
    test_cases: list[dict[str, Any]],
    interfaces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    steps = []
    for index, case in enumerate(test_cases, start=1):
        steps.append(_normalize_step({}, index, case, interfaces))
    return steps


def _generate_step_skeletons(
    test_cases: list[dict[str, Any]],
    llm_client: LLMClient,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = send_parallel(
        [
            {
                "messages": [
                    {
                        "role": "system",
                        "content": "시험케이스별 시험 절차를 생성하세요. JSON으로 step_json_list를 반환하세요.",
                    },
                    {"role": "user", "content": str(case)},
                ]
            }
            for case in test_cases
        ],
        client=llm_client,
    )
    warnings: list[dict[str, Any]] = []
    if not result["success"]:
        return _fallback_steps(test_cases, []), [{"code": "TS_STEP_LLM_FAILED", "message": result["error"]["message"]}]

    steps: list[dict[str, Any]] = []
    for index, (case, response) in enumerate(zip(test_cases, result["data"]), start=1):
        generated = _parse_step_list(response)
        if not generated:
            warnings.append(
                {
                    "code": "TS_STEP_LLM_FALLBACK",
                    "message": f"시험 케이스 {index}의 Step을 기본값으로 대체했습니다.",
                }
            )
            generated = [{}]
        for step in generated:
            steps.append(_normalize_step(step, len(steps) + 1, case, []))
    return steps, warnings


def _generate_step_details(
    steps: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
    interfaces: list[dict[str, Any]],
    llm_client: LLMClient,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_by_id = {case["test_case_id"]: case for case in test_cases}
    result = send_parallel(
        [
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Step별 상세 시험 정보를 생성하세요. 시험항목, 사전조건, 입력값, 예상결과, 화면ID를 "
                            "reference_interface_json_list를 활용하여 채우고 JSON으로 step_detail_json을 반환하세요."
                        ),
                    },
                    {
                        "role": "user",
                        "content": str(
                            {
                                "step": step,
                                "test_case": case_by_id.get(step.get("test_case_id")),
                                "reference_interface_json_list": interfaces,
                            }
                        ),
                    },
                ]
            }
            for step in steps
        ],
        client=llm_client,
    )
    warnings: list[dict[str, Any]] = []
    if not result["success"]:
        return [
            _normalize_step(step, index, case_by_id.get(step.get("test_case_id")), interfaces)
            for index, step in enumerate(steps, start=1)
        ], [{"code": "TS_STEP_DETAIL_LLM_FAILED", "message": result["error"]["message"]}]

    detailed: list[dict[str, Any]] = []
    for index, (step, response) in enumerate(zip(steps, result["data"]), start=1):
        parsed = _parse_step(response)
        if parsed is None:
            warnings.append(
                {
                    "code": "TS_STEP_DETAIL_FALLBACK",
                    "message": f"Step {index} 상세 정보를 기본값으로 대체했습니다.",
                }
            )
            parsed = step
        detailed.append(_normalize_step({**step, **parsed}, index, case_by_id.get(step.get("test_case_id")), interfaces))
    return detailed, warnings


def _find_interface(case: dict[str, Any], interfaces: list[dict[str, Any]]) -> dict[str, Any] | None:
    requirement_ids = set(map(str, case.get("source_requirement_ids", [])))
    for interface in interfaces:
        matched = interface.get("matched_requirement_ids") or interface.get("requirement_ids") or []
        if requirement_ids.intersection(map(str, matched)):
            return interface
    return interfaces[0] if interfaces else None


def _input_for_type(case_type: str) -> str:
    return "유효하지 않은 시험 데이터" if case_type in {"EXCEPTION", "INPUT_VALIDATION"} else "유효한 시험 데이터"


def _parse_step_list(response: Any) -> list[dict[str, Any]]:
    if not response or not response["success"]:
        return []
    parsed = parse_json_response(response["data"])
    if not parsed["success"]:
        return []
    value = parsed["data"]
    if isinstance(value, dict):
        value = value.get("step_json_list") or value.get("steps") or value.get("step_detail_json") or value.get("step")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _parse_step(response: Any) -> dict[str, Any] | None:
    steps = _parse_step_list(response)
    return steps[0] if steps else None


def _normalize_step(
    step: dict[str, Any],
    index: int,
    case: dict[str, Any] | None,
    interfaces: list[dict[str, Any]],
) -> dict[str, Any]:
    case = case or {}
    interface = _find_interface(case, interfaces) if case else None
    existing_screen_id = step.get("화면ID") or step.get("screen_id")
    interface_screen_id = (interface or {}).get("screen_id") or (interface or {}).get("interface_id")
    missing_screen_values = {None, "", "N/A", "None"}
    screen_id = str(
        (interface_screen_id or "N/A")
        if existing_screen_id in missing_screen_values
        else existing_screen_id or "N/A"
    )
    screen_description = str((interface or {}).get("description") or "")
    case_type = str(case.get("case_type") or step.get("case_type") or "NORMAL").upper()
    test_case_name = str(case.get("test_case_name") or step.get("시험항목") or "기능 검증")
    expected_result = (
        step.get("예상결과")
        or step.get("expected_result")
        or f"{case_type} 처리 결과가 요구사항과 일치해야 한다."
    )
    if screen_description and screen_description not in str(expected_result):
        expected_result = f"{expected_result} {screen_description}".strip()
    return {
        **step,
        "step_id": str(step.get("step_id") or f"STEP-{index:04d}"),
        "test_case_id": str(step.get("test_case_id") or case.get("test_case_id") or f"TC-{index:03d}"),
        "step_no": step.get("step_no") or index,
        "처리내용": step.get("처리내용") or step.get("process") or step.get("action") or f"{test_case_name}을 수행한다.",
        "시험항목": step.get("시험항목") or step.get("test_item") or test_case_name,
        "사전조건": step.get("사전조건") or step.get("precondition") or "시험 대상 시스템에 접근할 수 있어야 한다.",
        "입력값": step.get("입력값") or step.get("input") or step.get("input_value") or _input_for_type(case_type),
        "예상결과": expected_result,
        "화면ID": screen_id,
        "screen_id": screen_id,
    }
