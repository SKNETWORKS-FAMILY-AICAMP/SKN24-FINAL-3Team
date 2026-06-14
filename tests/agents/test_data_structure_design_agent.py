import unittest

from agents.data_structure_design.agent import DataStructureDesignAgent
from agents.validation.agent import ValidationAgent
from tools.result import success_result


class FakeDataLLM:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        return success_result({"analysis": "ok"})


class FakeStructuredDataLLM:
    def chat(self, messages, **kwargs):
        system_prompt = messages[0]["content"]
        if "요구사항 그룹 분석" in system_prompt:
            return success_result(
                {
                    "domain_group": {
                        "domain_name": "사용자 관리",
                        "source_requirement_ids": ["REQ-001"],
                        "description": "사용자 관리 도메인",
                    }
                }
            )
        if "엔티티 후보" in system_prompt:
            return success_result(
                {
                    "entity": {
                        "logical_name": "사용자",
                        "description": "사용자 엔티티",
                        "source_requirement_ids": ["REQ-001"],
                    }
                }
            )
        if "테이블 후보" in system_prompt:
            return success_result(
                {
                    "table": {
                        "logical_name": "사용자",
                        "physical_name": "tbl_user",
                        "columns": [
                            {
                                "logical_name": "사용자 번호",
                                "physical_name": "user_sn",
                                "data_type": "BIGINT",
                                "nullable": False,
                                "constraints": ["PK"],
                            }
                        ],
                    }
                }
            )
        if "컬럼 후보" in system_prompt:
            return success_result(
                {
                    "table": {
                        "logical_name": "사용자",
                        "physical_name": "tbl_user",
                        "columns": [
                            {
                                "logical_name": "사용자 번호",
                                "physical_name": "user_sn",
                                "data_type": "BIGINT",
                                "nullable": False,
                                "constraints": ["PK"],
                            },
                            {
                                "logical_name": "사용자 아이디",
                                "physical_name": "user_id",
                                "data_type": "VARCHAR(100)",
                                "nullable": False,
                                "constraints": [],
                            },
                        ],
                    }
                }
            )
        if "PK/FK 관계" in system_prompt:
            return success_result({"relationship_list": []})
        if "ERD JSON" in system_prompt:
            return success_result({})
        if "Mermaid용 ERD" in system_prompt:
            return success_result({"entities": [{"name": "tbl_user", "columns": []}], "relationships": []})
        return success_result({})


class DataStructureDesignAgentTest(unittest.TestCase):
    def test_erd_create_builds_tables_relationships_mermaid_and_uses_rag(self) -> None:
        calls = []

        def search_tool(query, **kwargs):
            calls.append((query, kwargs))
            return success_result({"normalized_results": [{"content": "표준 컬럼명"}]})

        state = {
            "project_sn": 1,
            "docs_cd": "ERD",
            "udt_yn": "N",
            "agent_outputs": {
                "document_merge_agent": {
                    "integrated_requirement_json_list": [
                        {
                            "req_id": "REQ-001",
                            "req_name": "사용자 관리",
                            "requirement_type": "기능",
                            "detail_text": "사용자 정보를 관리한다.",
                        },
                        {
                            "req_id": "REQ-002",
                            "req_name": "문서 관리",
                            "requirement_type": "기능",
                            "detail_text": "문서를 관리한다.",
                        },
                        {
                            "req_id": "NFR-001",
                            "req_name": "개인정보 보관",
                            "requirement_type": "비기능",
                            "detail_text": "개인정보 이력을 보관한다.",
                        },
                    ]
                }
            },
        }
        result = DataStructureDesignAgent(search_tool=search_tool).execute(state)

        tables = result["erd_entity_json"]["tables"]
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreaterEqual(len(tables), 2)
        self.assertTrue(all("PK" in table["columns"][0]["constraints"] for table in tables))
        self.assertTrue(result["erd_entity_json"]["relationships"])
        self.assertTrue(result["erd_mermaid_json"]["entities"])
        self.assertTrue(all(call[1]["search_targets"] == "RAG" for call in calls))
        self.assertIs(state["agent_outputs"]["data_structure_design_agent"], result)
        self.assertNotIn("erd_entity_json", state)

    def test_erd_update_preserves_existing_and_adds_meeting_entity(self) -> None:
        state = {
            "docs_cd": "ERD",
            "udt_yn": "Y",
            "agent_outputs": {
                "document_merge_agent": {
                    "existing_output_raw_json": {
                        "tables": [{"logical_name": "사용자", "physical_name": "tbl_user"}]
                    },
                    "meeting_change_items": [
                        {
                            "change_type": "ADD",
                            "item": {"logical_name": "문서", "physical_name": "tbl_docs"},
                        }
                    ],
                }
            },
        }
        result = DataStructureDesignAgent().execute(state)
        names = {table["physical_name"] for table in result["erd_entity_json"]["tables"]}

        self.assertEqual(names, {"tbl_user", "tbl_docs"})

    def test_erd_create_uses_parallel_llm_domain_entity_table_and_column_stages(self) -> None:
        state = {
            "project_sn": 1,
            "docs_cd": "ERD",
            "udt_yn": "N",
            "agent_outputs": {
                "document_merge_agent": {
                    "integrated_requirement_json_list": [
                        {
                            "req_id": "REQ-001",
                            "req_name": "사용자 관리",
                            "requirement_type": "기능",
                            "detail_text": "사용자를 관리한다.",
                        }
                    ]
                }
            },
        }
        result = DataStructureDesignAgent(
            llm_client=FakeStructuredDataLLM(),
            search_tool=lambda query, **kwargs: success_result({"normalized_results": [{"content": "user_id", "score": 0.9}]}),
        ).execute(state)

        table = result["erd_entity_json"]["tables"][0]
        self.assertEqual(table["physical_name"], "tbl_user")
        self.assertIn("user_id", {column["physical_name"] for column in table["columns"]})
        self.assertEqual(result["erd_mermaid_json"]["entities"][0]["name"], "tbl_user")

    def test_db_create_converts_reference_erd_and_passes_db_validator(self) -> None:
        state = {
            "docs_cd": "DB",
            "udt_yn": "N",
            "agent_outputs": {
                "document_merge_agent": {
                    "reference_erd_json_list": [
                        {
                            "table_id": "T1",
                            "logical_name": "사용자",
                            "physical_name": "tbl_user",
                            "columns": [
                                {
                                    "column_id": "C1",
                                    "logical_name": "사용자 번호",
                                    "physical_name": "user_sn",
                                    "data_type": "BIGINT",
                                    "nullable": False,
                                    "constraints": ["PK"],
                                }
                            ],
                        }
                    ]
                }
            },
        }
        result = DataStructureDesignAgent().execute(state)
        validation = ValidationAgent().execute(state)

        self.assertEqual(result["db_design_json"]["tables"][0]["table_name"], "tbl_user")
        self.assertEqual(validation["validation_result"]["validation_status"], "PASS")

    def test_db_update_normalizes_nested_artifact_and_debug_is_optional(self) -> None:
        state = {
            "docs_cd": "DB",
            "udt_yn": "Y",
            "etc": {"debug": True},
            "agent_outputs": {
                "document_merge_agent": {
                    "integrated_artifact_json_list": [
                        {
                            "tables": [
                                {
                                    "table_name": "tbl_docs",
                                    "table_description": "문서",
                                    "columns": [
                                        {
                                            "column_name": "docs_sn",
                                            "data_type": "BIGINT",
                                            "nullable": False,
                                            "default": None,
                                            "description": "문서 번호",
                                        }
                                    ],
                                }
                            ]
                        }
                    ]
                }
            },
        }
        result = DataStructureDesignAgent().execute(state)

        self.assertEqual(result["db_design_json"]["tables"][0]["table_name"], "tbl_docs")
        self.assertIn("source_artifacts", result["debug"])

    def test_missing_inputs_fail(self) -> None:
        erd = DataStructureDesignAgent().execute({"docs_cd": "ERD", "udt_yn": "N"})
        db = DataStructureDesignAgent().execute({"docs_cd": "DB", "udt_yn": "N"})

        self.assertEqual(erd["failure_type"], "ERD_REQUIREMENT_MISSING")
        self.assertEqual(db["failure_type"], "DB_REFERENCE_ERD_MISSING")

    def test_parallel_llm_analysis_is_used_when_client_is_injected(self) -> None:
        llm = FakeDataLLM()
        state = {
            "docs_cd": "DB",
            "udt_yn": "N",
            "etc": {"debug": True},
            "agent_outputs": {
                "document_merge_agent": {
                    "reference_erd_json_list": [
                        {"logical_name": "사용자", "physical_name": "tbl_user"}
                    ]
                }
            },
        }
        result = DataStructureDesignAgent(llm_client=llm).execute(state)

        self.assertGreaterEqual(llm.calls, 3)
        self.assertEqual(result["debug"]["llm_analysis"], {"analysis": "ok"})


if __name__ == "__main__":
    unittest.main()
