import unittest

from agents.requirement_generation.agent import RequirementGenerationAgent
from agents.requirement_generation.processors.requirement_refiner import (
    normalize_task3_output,
)
from tools.result import success_result


class FakeSLLM:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        system = messages[0]["content"]
        if "RAG query" in system:
            return success_result({"query": "로그인 보안 정책 비밀번호 실패 계정 잠금"})
        if "최종 요구사항 JSON" in system:
            return success_result(
                {
                    "requirement_id": "LOGIN-001",
                    "requirement_name": "사용자 로그인",
                    "requirement_type": "기능",
                    "description": "사용자는 계정으로 로그인할 수 있어야 한다.",
                    "source": ["SFR-001"],
                    "constraints": ["로그인 실패 5회 시 계정을 잠가야 한다."],
                    "priority": "미지정",
                    "validation_criteria": ["로그인 실패 5회 시 계정 잠금 여부를 확인한다."],
                    "note": "RAG 검색 결과를 반영함",
                }
            )
        return success_result(
            {
                "split_function_requirement_list": [
                    {
                        "requirement_id": "LOGIN-001",
                        "requirement_name": "사용자 로그인",
                        "description": "사용자는 계정으로 로그인할 수 있어야 한다.",
                        "source": ["SFR-001"],
                    }
                ]
            }
        )


class RequirementGenerationAgentTest(unittest.TestCase):
    def test_generation_filters_functions_calls_sllm_and_enriches_from_rag(self) -> None:
        llm = FakeSLLM()
        search_calls = []

        def search_tool(query, **kwargs):
            search_calls.append((query, kwargs))
            return success_result(
                {
                    "normalized_results": [
                        {"content": "로그인 실패 5회 시 계정을 잠가야 한다."},
                        {"content": "로그인 응답은 3초 이내여야 한다."},
                    ]
                }
            )

        state = _state(debug=False)
        result = RequirementGenerationAgent(
            llm_client=llm,
            search_tool=search_tool,
        ).execute(state)

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(len(llm.calls), 3)
        self.assertIn("SFR-001", llm.calls[0][1]["content"])
        self.assertNotIn("NFR-001", llm.calls[0][1]["content"])
        self.assertEqual(search_calls[0][1]["search_targets"], "RAG")
        self.assertEqual(search_calls[0][1]["filters"]["project_sn"], 1)
        self.assertEqual(search_calls[0][0], "로그인 보안 정책 비밀번호 실패 계정 잠금")
        item = result["final_requirement_json_list"][0]
        self.assertEqual(item["constraints"][0], "로그인 실패 5회 시 계정을 잠가야 한다.")
        self.assertEqual(item["validation_criteria"], ["로그인 실패 5회 시 계정 잠금 여부를 확인한다."])
        self.assertEqual(item["req_id"], item["requirement_id"])
        self.assertIs(state["agent_outputs"]["requirement_generation_agent"], result)
        self.assertNotIn("debug", result)

    def test_parallel_rag_reduces_duplicates_and_low_scores(self) -> None:
        def search_tool(query, **kwargs):
            return success_result(
                {
                    "normalized_results": [
                        {"content": "중복 정책", "score": 0.9},
                        {"content": "중복 정책", "score": 0.8},
                        {"content": "낮은 관련도", "score": 0.1},
                    ]
                }
            )

        result = RequirementGenerationAgent(search_tool=search_tool).execute(_state(debug=True))

        rag_results = result["debug"]["rag_searches"][0]["normalized_results"]
        self.assertEqual([item["content"] for item in rag_results], ["중복 정책"])
        self.assertEqual(result["final_requirement_json_list"][0]["constraints"], ["중복 정책"])

    def test_debug_intermediates_are_only_saved_when_enabled(self) -> None:
        result = RequirementGenerationAgent(
            search_tool=lambda query, **kwargs: success_result({"normalized_results": []})
        ).execute(_state(debug=True))

        self.assertIn("debug", result)
        self.assertIn("split_function_requirement_list", result["debug"])
        self.assertIn("rag_searches", result["debug"])

    def test_rag_failure_keeps_final_result_and_returns_warning(self) -> None:
        def failed_search(query, **kwargs):
            return {
                "success": False,
                "data": None,
                "error": {"code": "RAG_FAILED", "message": "검색 실패", "details": None},
            }

        result = RequirementGenerationAgent(search_tool=failed_search).execute(_state())

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["final_requirement_json_list"][0]["constraints"], ["응답시간 - 3초 이내 응답한다."])
        self.assertEqual(result["warnings"][0]["code"], "REQUIREMENT_RAG_SEARCH_FAILED")

    def test_empty_rag_uses_non_functional_source_requirements_as_constraints(self) -> None:
        result = RequirementGenerationAgent(
            search_tool=lambda query, **kwargs: success_result({"normalized_results": []})
        ).execute(_state())

        item = result["final_requirement_json_list"][0]
        self.assertIn("응답시간 - 3초 이내 응답한다.", item["constraints"])
        self.assertIn("응답시간 - 3초 이내 응답한다 준수 여부를 확인한다.", item["validation_criteria"])

    def test_invalid_mode_and_missing_input_fail(self) -> None:
        invalid = RequirementGenerationAgent().execute({"docs_cd": "DB", "udt_yn": "N"})
        missing = RequirementGenerationAgent().execute({"docs_cd": "SRS", "udt_yn": "N"})

        self.assertEqual(invalid["failure_type"], "REQUIREMENT_GENERATION_INVALID_MODE")
        self.assertEqual(missing["failure_type"], "INTEGRATED_REQUIREMENT_MISSING")

    def test_task3_output_is_normalized_for_cbd_document(self) -> None:
        normalized = normalize_task3_output(
            {
                "final_requirements": [
                    {
                        "gold_id": "GOLD-001",
                        "action_type": "산출",
                        "requirement_name": "CXL 메모리 프레임워크",
                        "requirement_detail": "CXL 메모리 프레임워크를 설계하여야 한다.",
                        "source_task2_ids": ["T2-000001"],
                        "source_atomic_ids": ["SFR-001::SFR-001-001"],
                        "sources": ["SFR-001", "SFR-003"],
                        "processing_type": "통합",
                        "merge_basis": "중복 기능을 통합함.",
                    }
                ]
            }
        )

        item = normalized[0]
        self.assertEqual(item["requirement_id"], "GOLD-001")
        self.assertEqual(item["action_type"], "산출")
        self.assertEqual(item["description"], "CXL 메모리 프레임워크를 설계하여야 한다.")
        self.assertEqual(item["source"], ["SFR-001", "SFR-003"])
        self.assertEqual(item["note"], "중복 기능을 통합함.")
        self.assertNotIn("source_task2_ids", item)
        self.assertNotIn("source_atomic_ids", item)


def _state(debug=False):
    return {
        "project_sn": 1,
        "docs_cd": "SRS",
        "udt_yn": "N",
        "etc": {"debug": debug},
        "agent_outputs": {
            "document_merge_agent": {
                "integrated_requirement_json_list": [
                    {
                        "req_id": "SFR-001",
                        "req_name": "로그인",
                        "requirement_type": "기능",
                        "detail_text": "사용자가 로그인한다.",
                        "source_req_ids": ["RFP-001"],
                    },
                    {
                        "req_id": "NFR-001",
                        "req_name": "응답시간",
                        "requirement_type": "성능",
                        "detail_text": "3초 이내 응답한다.",
                        "source_req_ids": ["RFP-002"],
                    },
                ]
            }
        },
    }


if __name__ == "__main__":
    unittest.main()
