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
            "validation_criteria": ["로그인 성공 여부를 확인한다."],
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

    def test_srs_accepts_canonical_requirement_fields(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "SRS",
                "agent_outputs": {
                    "requirement_generation_agent": {
                        "final_requirement_json_list": [
                            {
                                "requirement_id": "REQ-001",
                                "requirement_name": "로그인",
                                "requirement_type": "기능",
                                "description": "사용자가 로그인한다.",
                                "source": ["RFP-001"],
                                "validation_criteria": ["로그인 성공 여부 확인"],
                            },
                            {
                                "requirement_id": "NFR-001",
                                "requirement_name": "응답시간",
                                "requirement_type": "성능",
                                "description": "3초 이내 응답",
                                "source": ["RFP-002"],
                            },
                        ]
                    }
                },
            }
        )

        self.assertEqual(result["validation_result"]["validation_status"], "PASS")

    def test_srs_function_type_prefix_and_constraints_satisfy_nfr_check(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "SRS",
                "agent_outputs": {
                    "requirement_generation_agent": {
                        "final_requirement_json_list": [
                            {
                                "requirement_id": "REQ-001",
                                "requirement_name": "로그인",
                                "requirement_type": "기능 요구사항",
                                "description": "사용자가 로그인한다.",
                                "source": ["RFP-001"],
                                "constraints": ["3초 이내 응답한다."],
                                "validation_criteria": ["3초 이내 응답 여부 확인"],
                            }
                        ]
                    }
                },
            }
        )

        self.assertEqual(result["validation_result"]["validation_status"], "PASS")

    def test_srs_update_validates_document_merge_output(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "SRS",
                "udt_yn": "Y",
                "agent_outputs": {
                    "document_merge_agent": {
                        "integrated_artifact_json_list": [
                            {
                                "requirement_id": "SFR-001",
                                "requirement_name": "로그인 수정",
                                "requirement_type": "기능",
                                "description": "사용자가 로그인한다.",
                                "source": ["SFR-001"],
                                "validation_criteria": ["로그인 성공 여부 확인"],
                            },
                            {
                                "requirement_id": "NFR-001",
                                "requirement_name": "응답시간",
                                "requirement_type": "성능",
                                "description": "3초 이내 응답",
                                "source": ["NFR-001"],
                            },
                        ]
                    }
                },
            }
        )

        self.assertEqual(result["validation_result"]["validation_status"], "PASS")

    def test_srs_update_reports_non_object_items_as_schema_error(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "SRS",
                "udt_yn": "Y",
                "agent_outputs": {
                    "document_merge_agent": {
                        "integrated_artifact_json_list": [
                            "잘못 들어온 문자열 항목",
                            {
                                "requirement_id": "SFR-001",
                                "requirement_name": "로그인 수정",
                                "requirement_type": "기능",
                                "description": "사용자가 로그인한다.",
                                "source": ["SFR-001"],
                                "validation_criteria": ["로그인 성공 여부 확인"],
                            },
                        ]
                    }
                },
            }
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(_failure(result, "SRS_SCHEMA_ERROR")["target_scope"], ["0"])

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

    def test_interface_unmapped_image_does_not_fail_requirement_mapping(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "INTERFACE",
                "agent_outputs": {
                    "image_analysis_agent": {
                        "interface_image_analysis_json_list": [
                            {
                                "screen_id": "SCR-004",
                                "screen_name": "참고 이미지",
                                "description": "요구사항과 매핑되지 않은 이미지입니다. 사용 여부 확인 필요",
                                "matched_requirement_ids": [],
                                "match_status": "UNMAPPED_IMAGE",
                                "image_path": "screen.png",
                            }
                        ]
                    }
                },
            }
        )

        self.assertEqual(result["validation_result"]["validation_status"], "PASS")

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

    def test_erd_update_reports_missing_meeting_data_structure_changes(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "ERD",
                "udt_yn": "Y",
                "agent_outputs": {
                    "document_merge_agent": {
                        "meeting_change_items": [
                            {
                                "change_id": "M-001",
                                "content": "사용자-권한 N:M 관계와 문서-태그 N:M 관계, RAG 버전 관리가 필요하다.",
                            }
                        ]
                    },
                    "data_structure_design_agent": {
                        "erd_entity_json": {
                            "tables": [
                                {
                                    "table_id": "TABLE-001",
                                    "logical_name": "사용자",
                                    "physical_name": "tbl_user",
                                    "source_requirement_ids": ["REQ-001"],
                                    "columns": [
                                        {
                                            "column_id": "COL-001-001",
                                            "logical_name": "사용자 번호",
                                            "physical_name": "user_sn",
                                            "data_type": "BIGINT",
                                            "nullable": False,
                                            "constraints": ["PK"],
                                        }
                                    ],
                                }
                            ],
                            "relationships": [],
                        },
                        "erd_mermaid_json": {"entities": [{"name": "tbl_user"}], "relationships": []},
                    },
                    "mermaid_generation_agent": {
                        "mermaid_code": "erDiagram\n tbl_user { BIGINT user_sn PK }",
                        "mermaid_image_path": "erd.png",
                    },
                },
            }
        )

        check = _failure(result, "ERD_MEETING_CHANGE_MISSING")
        self.assertEqual(check["target_agent"], "data_structure_design_agent")
        self.assertIn("tbl_user_role", check["missing_items"])
        self.assertIn("tbl_rag_version", check["missing_items"])
        self.assertTrue(check["meeting_change_requirements"])

    def test_erd_detects_generic_and_mismatched_entity_names(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "ERD",
                "agent_outputs": {
                    "data_structure_design_agent": {
                        "erd_entity_json": {
                            "tables": [
                                {
                                    "table_id": "TABLE-001",
                                    "entity_id": "ENTITY-001",
                                    "logical_name": "엔티티",
                                    "entity_name": "엔티티",
                                    "physical_name": "tbl_agent",
                                    "description": "Agent 정보를 관리한다.",
                                    "entity_description": "Agent 정보를 관리한다.",
                                    "source_requirement_ids": ["REQ-001"],
                                    "columns": [
                                        {
                                            "column_id": "COL-001-001",
                                            "logical_name": "AgentID",
                                            "attribute_name": "AgentID",
                                            "physical_name": "agent_sn",
                                            "data_type": "BIGINT",
                                            "nullable": False,
                                            "constraints": ["PK"],
                                        },
                                        {
                                            "column_id": "COL-001-002",
                                            "logical_name": "Agent명",
                                            "attribute_name": "Agent명",
                                            "physical_name": "agent_nm",
                                            "data_type": "VARCHAR",
                                            "nullable": False,
                                            "constraints": [],
                                        },
                                    ],
                                }
                            ],
                            "relationships": [],
                        },
                        "erd_mermaid_json": {"entities": [{"name": "엔티티"}], "relationships": []},
                    },
                    "mermaid_generation_agent": {
                        "mermaid_code": "erDiagram\n Agent { BIGINT AgentID PK }",
                        "mermaid_image_path": "erd.png",
                    },
                },
            }
        )

        self.assertEqual(_failure(result, "ENTITY_GENERIC_NAME")["target_scope"], ["ENTITY-001"])
        self.assertEqual(_failure(result, "ENTITY_NAME_MISMATCH")["target_scope"], ["ENTITY-001"])

    def test_erd_detects_attribute_and_description_mismatch(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "ERD",
                "agent_outputs": {
                    "data_structure_design_agent": {
                        "erd_entity_json": {
                            "tables": [
                                {
                                    "table_id": "TABLE-001",
                                    "entity_id": "ENTITY-001",
                                    "logical_name": "사용자",
                                    "entity_name": "사용자",
                                    "physical_name": "tbl_user",
                                    "description": "Agent 정보를 관리한다.",
                                    "entity_description": "Agent 정보를 관리한다.",
                                    "source_requirement_ids": ["REQ-001"],
                                    "columns": [
                                        {
                                            "column_id": "COL-001-001",
                                            "logical_name": "사용자ID",
                                            "attribute_name": "사용자ID",
                                            "physical_name": "user_sn",
                                            "data_type": "BIGINT",
                                            "nullable": False,
                                            "constraints": ["PK"],
                                        },
                                        {
                                            "column_id": "COL-001-002",
                                            "logical_name": "Agent명",
                                            "attribute_name": "Agent명",
                                            "physical_name": "agent_nm",
                                            "data_type": "VARCHAR",
                                            "nullable": False,
                                            "constraints": [],
                                        },
                                    ],
                                }
                            ],
                            "relationships": [],
                        },
                        "erd_mermaid_json": {"entities": [{"name": "사용자"}], "relationships": []},
                    },
                    "mermaid_generation_agent": {
                        "mermaid_code": "erDiagram\n 사용자 { BIGINT 사용자ID PK }",
                        "mermaid_image_path": "erd.png",
                    },
                },
            }
        )

        self.assertEqual(_failure(result, "ENTITY_ATTRIBUTE_MISMATCH")["target_scope"], ["ENTITY-001.COL-001-002"])
        self.assertEqual(_failure(result, "ENTITY_DESCRIPTION_MISMATCH")["target_scope"], ["ENTITY-001"])

    def test_erd_entity_consistency_ignores_audit_attributes_and_compound_description(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "ERD",
                "agent_outputs": {
                    "data_structure_design_agent": {
                        "erd_entity_json": {
                            "tables": [
                                {
                                    "table_id": "TABLE-001",
                                    "entity_id": "ENTITY-001",
                                    "logical_name": "사용자 알림",
                                    "entity_name": "사용자 알림",
                                    "physical_name": "tbl_user_notification",
                                    "description": "사용자에게 전달할 알림 정보를 관리한다.",
                                    "entity_description": "사용자에게 전달할 알림 정보를 관리한다.",
                                    "source_requirement_ids": ["REQ-001"],
                                    "columns": [
                                        {
                                            "column_id": "COL-001-001",
                                            "logical_name": "알림ID",
                                            "attribute_name": "알림ID",
                                            "physical_name": "notification_sn",
                                            "data_type": "BIGINT",
                                            "nullable": False,
                                            "constraints": ["PK"],
                                        },
                                        {
                                            "column_id": "COL-001-002",
                                            "logical_name": "등록자명",
                                            "attribute_name": "등록자명",
                                            "physical_name": "creatr_nm",
                                            "data_type": "VARCHAR",
                                            "nullable": True,
                                            "constraints": [],
                                        },
                                        {
                                            "column_id": "COL-001-003",
                                            "logical_name": "수정일시",
                                            "attribute_name": "수정일시",
                                            "physical_name": "udt_dt",
                                            "data_type": "DATETIME",
                                            "nullable": True,
                                            "constraints": [],
                                        },
                                    ],
                                }
                            ],
                            "relationships": [],
                        },
                        "erd_mermaid_json": {"entities": [{"name": "사용자 알림"}], "relationships": []},
                    },
                    "mermaid_generation_agent": {
                        "mermaid_code": "erDiagram\n 사용자알림 { BIGINT 알림ID PK }",
                        "mermaid_image_path": "erd.png",
                    },
                },
            }
        )

        failure_types = {
            check.get("failure_type")
            for check in result["validation_result"]["checks"]
            if check.get("status") == "FAIL"
        }
        self.assertNotIn("ENTITY_NAME_MISMATCH", failure_types)
        self.assertNotIn("ENTITY_ATTRIBUTE_MISMATCH", failure_types)
        self.assertNotIn("ENTITY_DESCRIPTION_MISMATCH", failure_types)

    def test_erd_table_id_duplicates_do_not_fail_when_physical_names_are_unique(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "ERD",
                "agent_outputs": {
                    "data_structure_design_agent": {
                        "erd_entity_json": {
                            "tables": [
                                {
                                    "table_id": "TABLE-020",
                                    "logical_name": "사용자",
                                    "physical_name": "tbl_user",
                                    "source_requirement_ids": ["REQ-001"],
                                    "columns": [
                                        {
                                            "column_id": "COL-001-001",
                                            "logical_name": "사용자 번호",
                                            "physical_name": "user_sn",
                                            "data_type": "BIGINT",
                                            "nullable": False,
                                            "constraints": ["PK"],
                                        }
                                    ],
                                },
                                {
                                    "table_id": "TABLE-020",
                                    "logical_name": "권한",
                                    "physical_name": "tbl_role",
                                    "source_requirement_ids": ["REQ-002"],
                                    "columns": [
                                        {
                                            "column_id": "COL-002-001",
                                            "logical_name": "권한 번호",
                                            "physical_name": "role_sn",
                                            "data_type": "BIGINT",
                                            "nullable": False,
                                            "constraints": ["PK"],
                                        }
                                    ],
                                },
                            ],
                            "relationships": [],
                        },
                        "erd_mermaid_json": {"entities": [{"name": "tbl_user"}, {"name": "tbl_role"}], "relationships": []},
                    },
                    "mermaid_generation_agent": {
                        "mermaid_code": "erDiagram",
                        "mermaid_image_path": "erd.png",
                    },
                },
            }
        )

        self.assertIsNone(_maybe_failure(result, "ERD_TABLE_DUPLICATED"))

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

    def test_validation_only_stores_its_own_output_in_state(self) -> None:
        state = {"docs_cd": "SRS", "agent_outputs": {}}
        original = copy.deepcopy(state)
        result = self.agent.execute(state)
        self.assertEqual(state["agent_outputs"]["validation_agent"], result)
        self.assertNotIn("validation_result", state)
        self.assertEqual(original["docs_cd"], state["docs_cd"])

    def test_top_level_status_matches_validation_status(self) -> None:
        result = self.agent.execute({"docs_cd": "SRS", "agent_outputs": {}})
        self.assertEqual(result["status"], result["validation_result"]["validation_status"])

    def test_ts_quality_traceability_failures_return_replan_targets(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "TS",
                "agent_outputs": {
                    "document_merge_agent": {
                        "integrated_requirement_json_list": [
                            {"req_id": "REQ-1", "requirement_type": "기능"}
                        ],
                        "reference_interface_json_list": [{"screen_id": "SCR-1"}],
                    },
                    "test_scenario_generation_agent": {
                        "integrated_test_scenario_json": {
                            "scenario_json_list": [{"scenario_id": "SC-1", "source_requirement_ids": []}],
                            "test_case_json_list": [{"test_case_id": "TC-1", "case_type": "NORMAL"}],
                            "step_json_list": [
                                {
                                    "step_id": "STEP-1",
                                    "test_case_id": "TC-1",
                                    "step_no": 1,
                                    "처리내용": "실행",
                                    "시험항목": "시험",
                                    "사전조건": "조건",
                                    "입력값": "입력",
                                    "예상결과": "결과",
                                    "화면ID": "SCR-X",
                                }
                            ],
                        }
                    },
                },
            }
        )
        self.assertEqual(_failure(result, "TS_REQUIREMENT_COVERAGE_MISSING")["target_agent"], "test_scenario_generation_agent")
        self.assertEqual(_failure(result, "TS_INTERFACE_MAPPING_MISSING")["target_agent"], "test_scenario_generation_agent")
        self.assertEqual(_failure(result, "TS_EXCEPTION_CASE_MISSING")["target_agent"], "test_scenario_generation_agent")

    def test_erd_db_arch_detailed_rules_are_present(self) -> None:
        erd = self.agent.execute(
            {
                "docs_cd": "ERD",
                "agent_outputs": {
                    "data_structure_design_agent": {
                        "erd_entity_json": {
                            "tables": [
                                {
                                    "table_id": "T1",
                                    "logical_name": "사용자",
                                    "physical_name": "Bad Name",
                                    "columns": [{"column_id": "C1", "logical_name": "ID", "physical_name": "Bad ID", "data_type": "INT", "nullable": False, "constraints": ["PK"]}],
                                }
                            ],
                            "relationships": [{"relationship_id": "R1", "parent_table": "missing", "child_table": "Bad Name"}],
                        },
                        "erd_mermaid_json": {"entities": [{"name": "Bad Name"}]},
                    },
                    "mermaid_generation_agent": {"mermaid_code": "erDiagram", "mermaid_image_path": "erd.png"},
                },
            }
        )
        arch = self.agent.execute(
            {
                "docs_cd": "ARCH",
                "agent_outputs": {
                    "architecture_analysis_agent": {
                        "architecture_structure_json": {
                            "overview": "개요",
                            "components": [{"component_id": "A"}, {"component_id": "B"}],
                            "relations": [{"source": "A", "target": "A"}],
                            "layers": ["app"],
                            "deployment_environment": "cloud",
                        },
                        "architecture_document_json": {"overview": "개요"},
                    },
                    "mermaid_generation_agent": {"mermaid_code": "flowchart TD", "mermaid_image_path": "arch.png"},
                },
            }
        )
        self.assertEqual(_failure(erd, "ERD_FK_INVALID")["target_agent"], "data_structure_design_agent")
        self.assertEqual(_failure(erd, "ERD_STANDARD_NAMING_ERROR")["target_agent"], "data_structure_design_agent")
        self.assertEqual(_failure(arch, "ARCH_COMPONENT_ISOLATED")["target_agent"], "architecture_analysis_agent")

    def test_db_detects_constraints_and_indexes_that_reference_missing_columns(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "DB",
                "agent_outputs": {
                    "data_structure_design_agent": {
                        "db_design_json": {
                            "tables": [
                                {
                                    "table_name": "tbl_user",
                                    "table_description": "사용자",
                                    "columns": [
                                        {
                                            "column_name": "user_sn",
                                            "data_type": "BIGINT",
                                            "nullable": False,
                                            "default": None,
                                            "description": "사용자 번호",
                                        }
                                    ],
                                    "constraints": [{"type": "PK", "columns": ["missing_column"]}],
                                    "indexes": [{"name": "idx_missing", "columns": ["missing_column"]}],
                                }
                            ]
                        }
                    }
                },
            }
        )

        self.assertEqual(_failure(result, "DB_CONSTRAINT_INVALID")["target_scope"], ["tbl_user"])
        self.assertEqual(_failure(result, "DB_INDEX_INVALID")["target_scope"], ["tbl_user"])

    def test_db_reference_validation_ignores_column_id_and_compares_erd_column_specs(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "DB",
                "agent_outputs": {
                    "document_merge_agent": {
                        "reference_erd_json_list": [
                            {
                                "physical_name": "tbl_user",
                                "logical_name": "사용자",
                                "columns": [
                                    {
                                        "logical_name": "사용자 명",
                                        "physical_name": "user_nm",
                                        "data_type": "VARCHAR",
                                        "length": "100",
                                        "nullable": False,
                                        "constraints": [],
                                        "default": "",
                                    }
                                ],
                            }
                        ]
                    },
                    "data_structure_design_agent": {
                        "db_design_json": {
                            "tables": [
                                {
                                    "table_name": "tbl_user",
                                    "table_description": "사용자",
                                    "columns": [
                                        {
                                            "column_name": "user_nm",
                                            "column_id": "JJ_COL_001",
                                            "column_logical_name": "명",
                                            "data_type": "VARCHAR",
                                            "type_and_length": "VARCHAR(100)",
                                            "nullable": False,
                                            "not_null": "Y",
                                            "pk": "",
                                            "fk": "",
                                            "idx": "",
                                            "default": "",
                                            "description": "사용자 명",
                                            "constraint": "",
                                        }
                                    ],
                                    "constraints": [],
                                    "indexes": [],
                                }
                            ]
                        }
                    },
                },
            }
        )

        self.assertEqual(result["validation_result"]["validation_status"], "PASS")

    def test_db_reference_validation_detects_type_and_constraint_mismatches(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "DB",
                "agent_outputs": {
                    "document_merge_agent": {
                        "reference_erd_json_list": [
                            {
                                "physical_name": "tbl_file",
                                "logical_name": "파일",
                                "columns": [
                                    {
                                        "logical_name": "파일 크기",
                                        "physical_name": "file_size",
                                        "data_type": "NUMERIC",
                                        "length": "10",
                                        "nullable": False,
                                        "constraints": ["0 이상"],
                                        "default": "0",
                                    }
                                ],
                            }
                        ]
                    },
                    "data_structure_design_agent": {
                        "db_design_json": {
                            "tables": [
                                {
                                    "table_name": "tbl_file",
                                    "table_description": "파일",
                                    "columns": [
                                        {
                                            "column_name": "file_size",
                                            "column_id": "ANY_ID",
                                            "column_logical_name": "파일크기",
                                            "data_type": "VARCHAR",
                                            "type_and_length": "VARCHAR(20)",
                                            "nullable": True,
                                            "default": "",
                                            "description": "파일 크기",
                                            "constraint": "",
                                        }
                                    ],
                                    "constraints": [],
                                    "indexes": [],
                                }
                            ]
                        }
                    },
                },
            }
        )

        self.assertEqual(_failure(result, "DB_DATA_TYPE_MISSING")["target_scope"], ["tbl_file.file_size"])
        self.assertIn("tbl_file.file_size", _failure(result, "DB_CONSTRAINT_INVALID")["target_scope"])

    def test_db_reference_validation_normalizes_reference_pk_before_compare(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "DB",
                "agent_outputs": {
                    "document_merge_agent": {
                        "reference_erd_json_list": [
                            {
                                "logical_name": "생성형 기본사항 AI",
                                "physical_name": "tbl_create_ai",
                                "columns": [
                                    {
                                        "logical_name": "ID",
                                        "physical_name": "id",
                                        "data_type": "BIGINT",
                                        "nullable": False,
                                        "constraints": ["PK"],
                                    },
                                    {
                                        "logical_name": "컬럼내용",
                                        "physical_name": "cn",
                                        "data_type": "VARCHAR(4000)",
                                        "nullable": True,
                                        "constraints": [],
                                    },
                                ],
                            }
                        ]
                    },
                    "data_structure_design_agent": {
                        "db_design_json": {
                            "tables": [
                                {
                                    "table_name": "tbl_create_ai",
                                    "table_description": "생성형 기본사항 AI",
                                    "columns": [
                                        {
                                            "column_name": "create_ai_sn",
                                            "column_id": "ANY_ID",
                                            "column_logical_name": "ID",
                                            "data_type": "BIGINT",
                                            "type_and_length": "BIGINT",
                                            "nullable": False,
                                            "not_null": "Y",
                                            "pk": "Y",
                                            "fk": "",
                                            "idx": "Y",
                                            "default": "",
                                            "description": "ID",
                                            "constraint": "",
                                        },
                                        {
                                            "column_name": "cn",
                                            "column_id": "ANY_ID_2",
                                            "column_logical_name": "내용",
                                            "data_type": "VARCHAR",
                                            "type_and_length": "VARCHAR(4000)",
                                            "nullable": True,
                                            "default": "",
                                            "description": "컬럼내용",
                                            "constraint": "",
                                        },
                                    ],
                                    "constraints": [{"type": "PK", "columns": ["create_ai_sn"]}],
                                    "indexes": [],
                                }
                            ]
                        }
                    },
                },
            }
        )

        self.assertEqual(result["validation_result"]["validation_status"], "PASS")

    def test_arch_detects_relations_referencing_missing_components(self) -> None:
        result = self.agent.execute(
            {
                "docs_cd": "ARCH",
                "agent_outputs": {
                    "architecture_analysis_agent": {
                        "architecture_structure_json": {
                            "overview": "개요",
                            "components": [{"component_id": "WEB"}, {"component_id": "API"}],
                            "relations": [{"relation_id": "R1", "source": "WEB", "target": "MISSING"}],
                            "layers": ["app"],
                            "deployment_environment": "cloud",
                            "security": "보안",
                            "performance": "성능",
                            "operation": "운영",
                            "integration": "연계",
                            "deployment": "배포",
                        },
                        "architecture_document_json": {"overview": "개요"},
                    },
                    "mermaid_generation_agent": {"mermaid_code": "flowchart TD", "mermaid_image_path": "arch.png"},
                },
            }
        )

        self.assertEqual(_failure(result, "ARCH_RELATION_MISSING")["target_scope"], ["R1"])


def _failure(result, failure_type):
    return next(
        check
        for check in result["validation_result"]["checks"]
        if check["failure_type"] == failure_type
    )


def _maybe_failure(result, failure_type):
    return next(
        (
            check
            for check in result["validation_result"]["checks"]
            if check["failure_type"] == failure_type
        ),
        None,
    )


if __name__ == "__main__":
    unittest.main()
