import copy
import unittest

from agents.validation.agent import ValidationAgent


class ValidationAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = ValidationAgent()

    def test_srs_pass_and_partial_pass(self) -> None:
        functional = {
            "req_id": "SFR-001",
            "req_name": "로그인",
            "requirement_type": "기능",
            "detail_text": "사용자가 로그인한다.",
            "source_req_ids": ["RFP-001"],
        }
        non_functional = {
            **functional,
            "req_id": "NFR-001",
            "req_name": "응답시간",
            "requirement_type": "성능",
        }
        passed = self.agent.execute(
            {
                "docs_cd": "SRS",
                "agent_outputs": {
                    "requirement_generation_agent": {
                        "final_requirement_json_list": [functional, non_functional]
                    }
                },
            }
        )
        partial = self.agent.execute(
            {
                "docs_cd": "SRS",
                "agent_outputs": {
                    "requirement_generation_agent": {
                        "final_requirement_json_list": [functional]
                    }
                },
            }
        )

        self.assertEqual(passed["validation_result"]["validation_status"], "PASS")
        self.assertEqual(partial["validation_result"]["validation_status"], "PARTIAL_PASS")
        self.assertEqual(partial["validation_result"]["warning_count"], 1)

    def test_interface_failure_returns_target_agent_and_scope(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "INTERFACE",
                "agent_outputs": {
                    "image_analysis_agent": {
                        "interface_image_analysis_json_list": [
                            {
                                "screen_id": "SCR-001",
                                "screen_name": "로그인",
                                "description": "로그인 화면",
                                "matched_requirement_ids": ["SFR-001"],
                                "match_status": "MATCHED",
                            }
                        ]
                    }
                },
            }
        )
        check = _failure(result, "INTERFACE_IMAGE_MAPPING_MISSING")
        self.assertEqual(check["target_agent"], "image_analysis_agent")
        self.assertEqual(check["target_scope"], ["SCR-001"])

    def test_ts_detects_missing_step_detail(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "TS",
                "agent_outputs": {
                    "test_scenario_generation_agent": {
                        "integrated_test_scenario_json": {
                            "scenario_json_list": [{"scenario_id": "SC-1"}],
                            "test_case_json_list": [{"test_case_id": "TC-1"}],
                            "step_json_list": [{"step_id": "STEP-1", "처리내용": "실행"}],
                        }
                    }
                },
            }
        )
        self.assertEqual(
            _failure(result, "TS_STEP_DETAIL_MISSING")["target_scope"],
            ["STEP-1"],
        )

    def test_erd_detects_pk_and_mermaid_failures(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "ERD",
                "agent_outputs": {
                    "data_structure_design_agent": {
                        "erd_entity_json": {
                            "tables": [
                                {
                                    "table_id": "T1",
                                    "logical_name": "사용자",
                                    "physical_name": "users",
                                    "columns": [
                                        {
                                            "column_id": "C1",
                                            "logical_name": "이름",
                                            "physical_name": "name",
                                            "data_type": "varchar",
                                            "nullable": False,
                                            "constraints": [],
                                        }
                                    ],
                                }
                            ]
                        },
                        "erd_mermaid_json": {"tables": []},
                    },
                    "mermaid_generation_agent": {
                        "mermaid_code": "",
                        "mermaid_image_path": "",
                    },
                },
            }
        )
        self.assertEqual(_failure(result, "ERD_PK_MISSING")["target_agent"], "data_structure_design_agent")
        self.assertEqual(_failure(result, "ERD_MERMAID_RENDER_FAILED")["target_agent"], "mermaid_generation_agent")

    def test_db_and_arch_route_to_document_specific_validators(self) -> None:
        db = self.agent.execute(
            {
                "docs_cd": "DB",
                "agent_outputs": {
                    "data_structure_design_agent": {"db_design_json": {"tables": []}}
                },
            }
        )
        arch = self.agent.execute(
            {
                "docs_cd": "ARCH",
                "agent_outputs": {
                    "architecture_analysis_agent": {
                        "architecture_structure_json": {},
                        "architecture_document_json": {},
                    }
                },
            }
        )

        self.assertEqual(_failure(db, "DB_SCHEMA_ERROR")["target_agent"], "data_structure_design_agent")
        self.assertEqual(_failure(arch, "ARCH_SCHEMA_ERROR")["target_agent"], "architecture_analysis_agent")

    def test_validation_does_not_modify_state(self) -> None:
        state = {"docs_cd": "SRS", "agent_outputs": {}}
        original = copy.deepcopy(state)
        self.agent.execute(state)
        self.assertEqual(state, original)


def _failure(result, failure_type):
    return next(
        check
        for check in result["validation_result"]["checks"]
        if check["failure_type"] == failure_type
    )


if __name__ == "__main__":
    unittest.main()
