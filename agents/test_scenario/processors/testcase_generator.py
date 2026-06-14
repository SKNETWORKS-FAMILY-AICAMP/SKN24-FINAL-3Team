# 통합시험 시나리오별 시험 케이스를 생성하고 정제합니다.

from typing import Any

from tools.llm.llm_client import LLMClient
from tools.llm.response_parser import parse_json_response
from tools.llm.send_api import send_parallel


CASE_TYPES = ["NORMAL", "EXCEPTION", "AUTHORIZATION", "INPUT_VALIDATION", "STATE_CHANGE", "DATA_INTEGRITY"]


def generate_test_cases(
    scenarios: list[dict[str, Any]],
    *,
    llm_client: LLMClient | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if llm_client is None:
        return _fallback_cases_for_scenarios(scenarios), []

    result = send_parallel(
        [
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "시나리오별 통합시험 케이스를 생성하세요. 정상 처리, 예외 처리, 권한 검증, "
                            "입력값 검증, 승인 프로세스, 상태 변경, 인터페이스 연계, 데이터 정합성 검증을 "
                            "고려하고 JSON으로 test_case_json_list를 반환하세요."
                        ),
                    },
                    {"role": "user", "content": str(scenario)},
                ]
            }
            for scenario in scenarios
        ],
        client=llm_client,
    )
    warnings: list[dict[str, Any]] = []
    if not result["success"]:
        return _fallback_cases_for_scenarios(scenarios), [
            {"code": "TS_TEST_CASE_LLM_FAILED", "message": result["error"]["message"]}
        ]

    cases: list[dict[str, Any]] = []
    for scenario_index, (scenario, response) in enumerate(zip(scenarios, result["data"]), start=1):
        generated = _parse_case_list(response)
        if not generated:
            warnings.append(
                {
                    "code": "TS_TEST_CASE_LLM_FALLBACK",
                    "message": f"시나리오 {scenario_index}의 시험 케이스를 기본값으로 대체했습니다.",
                }
            )
            generated = _fallback_cases_for_scenario(scenario, scenario_index)
        cases.extend(
            _normalize_case(case, len(cases) + index + 1, scenario, scenario_index)
            for index, case in enumerate(generated)
        )
    return _ensure_case_type_coverage(cases, scenarios), warnings


def refine_test_cases(
    cases: list[dict[str, Any]],
    *,
    llm_client: LLMClient | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fallback = [_normalize_case(case, index, None, 1) for index, case in enumerate(cases, start=1)]
    if llm_client is None:
        return fallback, []

    result = send_parallel(
        [
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "시험 케이스별 품질을 검토하고 정제하세요. 정상 케이스, 예외 케이스, 권한 검증, "
                            "상태 변경 검증, 데이터 검증 존재 여부를 확인하고 JSON으로 test_case를 반환하세요."
                        ),
                    },
                    {"role": "user", "content": str(case)},
                ]
            }
            for case in cases
        ],
        client=llm_client,
    )
    warnings: list[dict[str, Any]] = []
    if not result["success"]:
        return fallback, [{"code": "TS_TEST_CASE_REVIEW_LLM_FAILED", "message": result["error"]["message"]}]

    refined: list[dict[str, Any]] = []
    for index, (case, response) in enumerate(zip(cases, result["data"]), start=1):
        parsed = _parse_case(response)
        if parsed is None:
            warnings.append(
                {
                    "code": "TS_TEST_CASE_REVIEW_FALLBACK",
                    "message": f"시험 케이스 {index} 품질 검토 결과를 기본값으로 대체했습니다.",
                }
            )
            parsed = case
        refined.append(_normalize_case(parsed, index, None, 1))
    return refined, warnings


def _fallback_cases_for_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = []
    for scenario_index, scenario in enumerate(scenarios, start=1):
        cases.extend(_fallback_cases_for_scenario(scenario, scenario_index))
    return cases


def _fallback_cases_for_scenario(scenario: dict[str, Any], scenario_index: int) -> list[dict[str, Any]]:
    return [
        {
            "test_case_id": f"TC-{scenario_index:03d}-{case_index:02d}",
            "scenario_id": scenario["scenario_id"],
            "case_type": case_type,
            "test_case_name": f"{scenario['scenario_name']} {case_type} 검증",
            "source_requirement_ids": scenario.get("source_requirement_ids", []),
        }
        for case_index, case_type in enumerate(CASE_TYPES, start=1)
    ]


def _parse_case_list(response: Any) -> list[dict[str, Any]]:
    if not response or not response["success"]:
        return []
    parsed = parse_json_response(response["data"])
    if not parsed["success"]:
        return []
    value = parsed["data"]
    if isinstance(value, dict):
        value = value.get("test_case_json_list") or value.get("test_cases") or value.get("cases")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _parse_case(response: Any) -> dict[str, Any] | None:
    if not response or not response["success"]:
        return None
    parsed = parse_json_response(response["data"])
    if not parsed["success"]:
        return None
    value = parsed["data"]
    if isinstance(value, dict):
        value = value.get("test_case") or value.get("case") or value
    return value if isinstance(value, dict) else None


def _normalize_case(
    case: dict[str, Any],
    index: int,
    scenario: dict[str, Any] | None,
    scenario_index: int,
) -> dict[str, Any]:
    scenario_id = str(case.get("scenario_id") or (scenario or {}).get("scenario_id") or f"SCN-{scenario_index:03d}")
    scenario_name = str((scenario or {}).get("scenario_name") or case.get("scenario_name") or "업무 시나리오")
    return {
        **case,
        "test_case_id": str(case.get("test_case_id") or f"TC-{index:03d}"),
        "scenario_id": scenario_id,
        "case_type": str(case.get("case_type") or "NORMAL").upper(),
        "test_case_name": str(case.get("test_case_name") or case.get("name") or f"{scenario_name} 시험 케이스 {index}"),
        "source_requirement_ids": case.get("source_requirement_ids") or (scenario or {}).get("source_requirement_ids", []),
    }


def _ensure_case_type_coverage(
    cases: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_scenario = {}
    for case in cases:
        by_scenario.setdefault(case["scenario_id"], []).append(case)

    covered: list[dict[str, Any]] = []
    for scenario_index, scenario in enumerate(scenarios, start=1):
        scenario_cases = by_scenario.get(scenario["scenario_id"], [])
        existing_types = {case["case_type"] for case in scenario_cases}
        scenario_cases.extend(
            case
            for case in _fallback_cases_for_scenario(scenario, scenario_index)
            if case["case_type"] not in existing_types
        )
        covered.extend(scenario_cases)
    return covered
