# ERD 및 DB 데이터 구조 설계 Agent의 실행 진입점입니다.

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any

from agents.data_structure_design.processors import (
    build_db_design,
    build_domain_groups,
    build_entity_candidates,
    build_erd_tables,
    build_relationships,
    filter_data_requirements,
    normalize_db_design,
    normalize_erd_tables,
)
from tools.llm.llm_client import LLMClient
from tools.llm.response_parser import parse_json_response
from tools.llm.send_api import send_parallel
from tools.result import ToolResult
from tools.search.search_router import search
from workflow.state import WorkflowState
from agents.data_structure_design.processors.column_standardizer import table_name


class DataStructureDesignAgent:
    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        search_tool: Callable[..., ToolResult] = search,
        max_parallel_workers: int = 4,
    ) -> None:
        self.llm_client = llm_client
        self.search_tool = search_tool
        self.max_parallel_workers = max(1, max_parallel_workers)

    def execute(self, state: WorkflowState) -> dict[str, Any]:
        docs_cd = str(state.get("docs_cd", "")).upper()
        mode = str(state.get("udt_yn", "")).upper()
        document_merge = state.get("agent_outputs", {}).get("document_merge_agent", {})
        if docs_cd == "ERD" and mode == "N":
            output = self._create_erd(document_merge, state)
        elif docs_cd == "ERD" and mode == "Y":
            output = self._update_erd(document_merge, state)
        elif docs_cd == "DB" and mode == "N":
            output = self._create_db(document_merge, state)
        elif docs_cd == "DB" and mode == "Y":
            output = self._update_db(document_merge, state)
        else:
            output = self._failed("DATA_STRUCTURE_INVALID_MODE", f"지원하지 않는 실행 조건입니다: {docs_cd}/{mode}")
        return self._store(state, output)

    def _create_erd(self, document_merge: dict[str, Any], state: WorkflowState) -> dict[str, Any]:
        requirements = document_merge.get("integrated_requirement_json_list")
        if not isinstance(requirements, list) or not requirements:
            return self._failed("ERD_REQUIREMENT_MISSING", "integrated_requirement_json_list가 필요합니다.")
        selected = filter_data_requirements(requirements)
        if not selected:
            return self._failed("ERD_DATA_REQUIREMENT_MISSING", "데이터 구조 설계 대상 요구사항이 없습니다.")
        groups, group_warnings = self._build_domain_groups(selected)
        entities, entity_warnings = self._build_entity_candidates(groups)
        tables, table_warnings = self._build_table_candidates(entities)
        warnings, rag_results = self._standard_search(tables, state)
        tables, column_warnings = self._build_column_candidates(tables, rag_results)
        relationships, relationship_warnings = self._build_relationships(tables)
        erd_entity_json, erd_warnings = self._build_final_erd_json(tables, relationships)
        erd_mermaid_json, mermaid_warnings = self._build_erd_mermaid_json(erd_entity_json)
        warnings.extend([*group_warnings, *entity_warnings, *table_warnings, *column_warnings, *relationship_warnings, *erd_warnings, *mermaid_warnings])
        return self._erd_success(
            state,
            erd_entity_json,
            erd_mermaid_json,
            warnings,
            {
                "domain_group_list": groups,
                "entity_candidate_list": entities,
                "table_candidate_list": tables,
                "rag_results": rag_results,
            },
        )

    def _update_erd(self, document_merge: dict[str, Any], state: WorkflowState) -> dict[str, Any]:
        existing = document_merge.get("existing_output_raw_json")
        changes = document_merge.get("meeting_change_items")
        if not isinstance(existing, dict) or not existing:
            return self._failed("ERD_EXISTING_OUTPUT_MISSING", "existing_output_raw_json이 필요합니다.")
        if not isinstance(changes, list):
            return self._failed("ERD_MEETING_CHANGE_MISSING", "meeting_change_items가 필요합니다.")
        existing_analysis = self._llm_dict("기존 ERD 구조를 분석하세요.", {"existing_output_raw_json": existing}, "ERD_EXISTING_ANALYSIS_LLM_FAILED")
        tables = normalize_erd_tables(_extract_tables(existing_analysis or existing))
        llm_analysis, warnings = self._parallel_llm_analysis(changes, "회의록 변경사항의 ERD 엔티티, 컬럼, 관계 영향을 분석하세요.")
        tables = _apply_table_changes(tables, changes)
        redesign = self._llm_dict(
            "기존 ERD와 회의록 변경사항을 기반으로 ERD를 재설계하고 JSON으로 반환하세요.",
            {"tables": tables, "meeting_change_items": changes, "llm_analysis": llm_analysis},
            "ERD_REDESIGN_LLM_FAILED",
        )
        tables = normalize_erd_tables(_extract_tables(redesign) or tables)
        relationships, relationship_warnings = self._build_relationships(tables)
        erd_entity_json, erd_warnings = self._build_final_erd_json(tables, relationships)
        erd_mermaid_json, mermaid_warnings = self._build_erd_mermaid_json(erd_entity_json)
        warnings.extend([*relationship_warnings, *erd_warnings, *mermaid_warnings])
        return self._erd_success(
            state,
            erd_entity_json,
            erd_mermaid_json,
            warnings,
            {"meeting_change_items": changes, "llm_analysis": llm_analysis},
        )

    def _create_db(self, document_merge: dict[str, Any], state: WorkflowState) -> dict[str, Any]:
        reference = document_merge.get("reference_erd_json_list")
        if not isinstance(reference, list) or not reference:
            return self._failed("DB_REFERENCE_ERD_MISSING", "reference_erd_json_list가 필요합니다.")
        tables = normalize_erd_tables(reference)
        erd_analysis = self._llm_dict("ERD 구조를 분석하세요. 테이블, 컬럼, PK, FK, 관계를 JSON으로 반환하세요.", {"tables": tables}, "DB_ERD_ANALYSIS_LLM_FAILED")
        design, warnings = self._build_db_specifications(tables)
        final_design, final_warnings = self._finalize_db_design(design)
        warnings.extend(final_warnings)
        return self._db_success(state, final_design, warnings, {"reference_erd_json_list": reference, "llm_analysis": erd_analysis})

    def _update_db(self, document_merge: dict[str, Any], state: WorkflowState) -> dict[str, Any]:
        artifacts = document_merge.get("integrated_artifact_json_list")
        if not isinstance(artifacts, list) or not artifacts:
            return self._failed("DB_ARTIFACT_MISSING", "integrated_artifact_json_list가 필요합니다.")
        existing_analysis = self._llm_dict("기존 DB 설계서 구조를 분석하세요.", {"integrated_artifact_json_list": artifacts}, "DB_EXISTING_ANALYSIS_LLM_FAILED")
        llm_analysis, warnings = self._parallel_llm_analysis(artifacts, "기존 DB 설계서의 컬럼, 제약조건, 인덱스 변경사항을 검토하세요.")
        analyzed_tables = _extract_tables(existing_analysis) if existing_analysis else []
        design = normalize_db_design(analyzed_tables or _flatten_tables(artifacts))
        final_design, final_warnings = self._finalize_db_design(design)
        warnings.extend(final_warnings)
        return self._db_success(
            state,
            final_design,
            warnings,
            {"source_artifacts": artifacts, "llm_analysis": llm_analysis},
        )

    def _build_domain_groups(
        self,
        requirements: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        fallback = build_domain_groups(requirements)
        generated, warnings = self._parallel_llm_list(
            requirements,
            (
                "너는 SI 프로젝트 데이터 모델러입니다. 요구사항을 시스템 전체 관점의 업무 도메인으로 묶으세요. "
                "기능 하나마다 도메인을 만들지 말고 사용자/권한, 문서/파일, AI 모델, 상담/대화, 통계/로그, "
                "연계/배치, 공통코드처럼 공유 데이터가 생기는 단위로 통합하세요. "
                "JSON으로 domain_group 또는 domain_group_list만 반환하세요."
            ),
            "domain_group",
            "domain_group_list",
            "ERD_DOMAIN_GROUP_LLM_FAILED",
        )
        return _normalize_domain_groups(generated or fallback), warnings

    def _build_entity_candidates(
        self,
        groups: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        fallback = build_entity_candidates(groups)
        generated, warnings = self._parallel_llm_list(
            groups,
            (
                "너는 통합 ERD 설계자입니다. 도메인별로 저장/관리 대상이 되는 핵심 엔티티 후보를 추출하세요. "
                "화면명이나 기능명을 그대로 엔티티로 만들지 말고, 중복/유사 개념은 하나로 병합하세요. "
                "각 엔티티는 entity_id(ENT-001 형식), logical_name, description(80자 이내 요약), "
                "source_requirement_ids를 포함하세요. JSON으로 entity 또는 entity_candidate_list만 반환하세요."
            ),
            "entity",
            "entity_candidate_list",
            "ERD_ENTITY_LLM_FAILED",
        )
        return _normalize_entities(generated or fallback), warnings

    def _build_table_candidates(
        self,
        entities: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        fallback = build_erd_tables(entities)
        generated, warnings = self._parallel_llm_list(
            entities,
            (
                "너는 공공 SI 프로젝트 DB 모델러입니다. 엔티티별 테이블 후보를 설계하세요. "
                "물리 테이블명은 소문자 snake_case이며 tbl_ 접두사를 사용하세요. "
                "entity_id는 ENT-001 형식으로 유지하고 description은 문서에 들어갈 1문장 요약으로 80자 이내로 작성하세요. "
                "각 테이블은 최소 6개 이상의 업무 컬럼을 가져야 하며, PK, 명칭/내용, 상태코드, 사용여부, 등록/수정일시 같은 "
                "공통 컬럼과 요구사항에서 도출한 핵심 업무 컬럼을 포함하세요. "
                "JSON으로 table 또는 table_candidate_list만 반환하세요."
            ),
            "table",
            "table_candidate_list",
            "ERD_TABLE_LLM_FAILED",
        )
        return normalize_erd_tables(generated or fallback), warnings

    def _build_column_candidates(
        self,
        tables: list[dict[str, Any]],
        rag_results: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rag_by_table = {item["table_id"]: item.get("normalized_results", []) for item in rag_results}
        generated, warnings = self._parallel_llm_list(
            [
                {
                    "table": table,
                    "rag_results": rag_by_table.get(table["table_id"], []),
                    "instruction": (
                        "공공데이터 표준, 컬럼 표준명, 용어사전을 반영해 컬럼 후보를 설계하세요. "
                        "컬럼은 6~20개 수준으로 설계하고, 한글 논리명/영문 물리명/데이터 타입/길이/PK/FK/NULL/설명을 포함하세요. "
                        "PK/FK 여부는 constraints 배열에는 PK/FK로 표시해도 되지만, description에는 업무 의미만 쓰세요."
                    ),
                }
                for table in tables
            ],
            (
                "테이블별 컬럼 후보를 설계하세요. 기능 요구사항의 입력값, 상태값, 이력, 파일, 권한, 검색 조건, "
                "연계 식별자를 컬럼으로 반영하고 2개짜리 축약 테이블을 만들지 마세요. "
                "JSON으로 table 또는 table_candidate_list를 반환하세요."
            ),
            "table",
            "table_candidate_list",
            "ERD_COLUMN_LLM_FAILED",
        )
        if not generated:
            return tables, warnings
        by_physical = {table["physical_name"]: table for table in tables}
        updated = []
        for item in generated:
            if not isinstance(item, dict):
                continue
            table = item.get("table") if isinstance(item.get("table"), dict) else item
            physical_name = str(table.get("physical_name") or table.get("table_name") or "")
            base = dict(by_physical.get(physical_name) or {})
            if item.get("column_candidate_list") and not table.get("columns"):
                table = {**table, "columns": item["column_candidate_list"]}
            base.update(table)
            updated.append(base)
        return normalize_erd_tables(updated or tables), warnings

    def _build_relationships(
        self,
        tables: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        fallback = build_relationships(tables)
        value = self._llm_dict(
            (
                "테이블 목록을 기준으로 PK/FK 관계를 설계하세요. 단순히 첫 번째 테이블을 모든 테이블의 부모로 만들지 말고 "
                "사용자-로그, 문서-파일, AI모델-세션, 코드-상태처럼 업무적으로 설명 가능한 관계만 생성하세요. "
                "JSON으로 relationship_list 또는 relationships를 반환하세요."
            ),
            {"tables": tables, "fallback_relationships": fallback},
            "ERD_RELATION_LLM_FAILED",
        )
        relationships = value.get("relationship_list") or value.get("relationships") if isinstance(value, dict) else None
        return relationships if isinstance(relationships, list) and relationships else fallback, []

    def _build_final_erd_json(
        self,
        tables: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        fallback = {"tables": tables, "relationships": relationships}
        value = self._llm_dict(
            (
                "전체 데이터 구조를 병합하여 ERD JSON을 생성하세요. "
                "테이블/컬럼 물리명은 소문자 snake_case, entity_id는 ENT-001 형식, table_id는 TABLE-001 형식을 유지하세요. "
                "description/table_description은 DOCX 엔티티 설명 칸에 들어갈 80자 이내 요약문이어야 합니다. "
                "엔티티당 컬럼은 최소 6개 이상을 유지하고, 중복 테이블은 병합하세요. JSON 객체만 반환하세요."
            ),
            fallback,
            "ERD_FINAL_JSON_LLM_FAILED",
        )
        if isinstance(value, dict):
            tables_value = _extract_tables(value)
            relationships_value = value.get("relationships") or value.get("relationship_list")
            if tables_value:
                normalized_tables = normalize_erd_tables(tables_value)
                return {
                    "tables": normalized_tables,
                    "relationships": _normalize_relationship_names(
                        relationships_value if isinstance(relationships_value, list) else relationships,
                        normalized_tables,
                    ),
                }, []
        return {
            "tables": normalize_erd_tables(fallback["tables"]),
            "relationships": _normalize_relationship_names(fallback["relationships"], normalize_erd_tables(fallback["tables"])),
        }, []

    def _build_erd_mermaid_json(
        self,
        erd_entity_json: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        fallback = {
            "entities": [
                {"name": table["physical_name"], "columns": table["columns"]}
                for table in erd_entity_json.get("tables", [])
            ],
            "relationships": erd_entity_json.get("relationships", []),
        }
        value = self._llm_dict("Mermaid용 ERD 구조 JSON을 생성하세요.", erd_entity_json, "ERD_MERMAID_JSON_LLM_FAILED")
        if isinstance(value, dict) and (value.get("entities") or value.get("tables")):
            return {
                "entities": value.get("entities") or [
                    {"name": table["physical_name"], "columns": table["columns"]}
                    for table in normalize_erd_tables(value.get("tables") or [])
                ],
                "relationships": value.get("relationships") or fallback["relationships"],
            }, []
        return fallback, []

    def _build_db_specifications(
        self,
        tables: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        fallback = build_db_design(tables)
        generated, warnings = self._parallel_llm_list(
            tables,
            "테이블별 DB 명세를 생성하세요. 테이블 설명, 컬럼 설명, 데이터 타입, 제약조건, Default, 인덱스를 JSON으로 반환하세요.",
            "table_specification",
            "table_specification_json",
            "DB_TABLE_SPEC_LLM_FAILED",
        )
        if not generated:
            return fallback, warnings
        return {"tables": [_normalize_db_table(item, index) for index, item in enumerate(generated)]}, warnings

    def _finalize_db_design(
        self,
        design: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        value = self._llm_dict("DB 설계서를 재정리하고 JSON으로 db_design_json을 반환하세요.", design, "DB_FINAL_JSON_LLM_FAILED")
        if isinstance(value, dict):
            candidate = value.get("db_design_json") or value
            if isinstance(candidate, dict) and isinstance(candidate.get("tables"), list):
                return {"tables": [_normalize_db_table(item, index) for index, item in enumerate(candidate["tables"])]}, []
        return design, []

    def _parallel_llm_list(
        self,
        items: list[Any],
        instruction: str,
        item_key: str,
        list_key: str,
        warning_code: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if self.llm_client is None or not items:
            return [], []
        result = send_parallel(
            [
                {"messages": [{"role": "system", "content": instruction}, {"role": "user", "content": str(item)}]}
                for item in items
            ],
            client=self.llm_client,
            max_workers=self.max_parallel_workers,
        )
        if not result["success"]:
            return [], [{"code": warning_code, "message": result["error"]["message"]}]
        output: list[dict[str, Any]] = []
        warnings = []
        for index, response in enumerate(result["data"]):
            parsed = parse_json_response(response["data"]) if response and response["success"] else None
            value = parsed["data"] if parsed and parsed["success"] else None
            extracted = _extract_llm_items(value, item_key, list_key)
            if extracted:
                output.extend(extracted)
            else:
                warnings.append({"code": warning_code, "message": f"LLM 항목 {index + 1} 결과를 기본값으로 대체합니다."})
        return output, warnings

    def _llm_dict(
        self,
        instruction: str,
        payload: Any,
        warning_code: str,
    ) -> dict[str, Any]:
        if self.llm_client is None:
            return {}
        result = self.llm_client.chat(
            [
                {"role": "system", "content": instruction},
                {"role": "user", "content": str(payload)},
            ]
        )
        if not result["success"]:
            return {}
        parsed = parse_json_response(result["data"])
        return parsed["data"] if parsed["success"] and isinstance(parsed["data"], dict) else {}

    def _parallel_llm_analysis(
        self,
        items: list[Any],
        instruction: str,
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        if self.llm_client is None or not items:
            return [], []
        result = send_parallel(
            [
                {
                    "messages": [
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": str(item)},
                    ]
                }
                for item in items
            ],
            client=self.llm_client,
            max_workers=self.max_parallel_workers,
        )
        if not result["success"]:
            return [], [{"code": "DATA_STRUCTURE_LLM_FAILED", "message": result["error"]["message"]}]
        analyses = []
        warnings = []
        for index, response in enumerate(result["data"]):
            parsed = parse_json_response(response["data"]) if response and response["success"] else None
            if parsed and parsed["success"]:
                analyses.append(parsed["data"])
            else:
                warnings.append({"code": "DATA_STRUCTURE_LLM_ITEM_FAILED", "message": f"LLM 분석 항목 {index + 1} 처리에 실패했습니다."})
        return analyses, warnings

    def _standard_search(
        self,
        tables: list[dict[str, Any]],
        state: WorkflowState,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        warnings = []
        results = []
        with ThreadPoolExecutor(max_workers=self.max_parallel_workers) as executor:
            future_map = {
                executor.submit(
                    self.search_tool,
                    f"{table['logical_name']} 공공데이터 컬럼 표준명 용어사전",
                    search_targets="RAG",
                    filters={
                        "domain": "public_data",
                        "doc_type": ["standard_term", "standard_word", "standard_domain", "db_standard_manual"],
                    },
                ): table
                for table in tables
            }
            for future in as_completed(future_map):
                table = future_map[future]
                try:
                    result = future.result()
                except Exception as exc:
                    warnings.append({"code": "DATA_STANDARD_RAG_FAILED", "message": str(exc), "table_id": table["table_id"]})
                    continue
                if result["success"]:
                    results.append({"table_id": table["table_id"], "normalized_results": _dedupe_results(result["data"]["normalized_results"])})
                else:
                    warnings.append({"code": "DATA_STANDARD_RAG_FAILED", "message": result["error"]["message"], "table_id": table["table_id"]})
        return warnings, results

    @staticmethod
    def _erd_success(state, erd_entity_json, erd_mermaid_json, warnings, debug):
        output = {
            "status": "SUCCESS",
            "erd_entity_json": erd_entity_json,
            "erd_mermaid_json": erd_mermaid_json,
            "warnings": warnings,
            "errors": [],
        }
        if bool(state.get("etc", {}).get("debug")):
            output["debug"] = debug
        return output

    @staticmethod
    def _db_success(state, design, warnings, debug):
        output = {"status": "SUCCESS", "db_design_json": design, "warnings": warnings, "errors": []}
        if bool(state.get("etc", {}).get("debug")):
            output["debug"] = debug
        return output

    @staticmethod
    def _store(state: WorkflowState, output: dict[str, Any]) -> dict[str, Any]:
        state.setdefault("agent_outputs", {})["data_structure_design_agent"] = output
        return output

    @staticmethod
    def _failed(code: str, message: str) -> dict[str, Any]:
        return {"status": "FAILED", "failure_type": code, "warnings": [], "errors": [{"code": code, "message": message}]}


def _extract_tables(document: dict[str, Any]) -> list[Any]:
    for key in ("tables", "entities", "erd_entity_json_list"):
        if isinstance(document.get(key), list):
            return document[key]
    return []


def _flatten_tables(items: list[Any]) -> list[Any]:
    tables: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            nested = _extract_tables(item)
            tables.extend(nested if nested else [item])
    return tables


def _apply_table_changes(tables: list[dict[str, Any]], changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updated = deepcopy(tables)
    for change in changes:
        operation = str(change.get("change_type") or change.get("operation") or "").upper()
        item = change.get("item")
        if operation == "ADD" and isinstance(item, dict):
            updated.extend(normalize_erd_tables([item]))
    return normalize_erd_tables(updated)


def _extract_llm_items(value: Any, item_key: str, list_key: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get(list_key), list):
            return [item for item in value[list_key] if isinstance(item, dict)]
        if isinstance(value.get(item_key), dict):
            return [value[item_key]]
        if isinstance(value.get("items"), list):
            return [item for item in value["items"] if isinstance(item, dict)]
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_domain_groups(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        name = str(item.get("domain_name") or item.get("name") or item.get("group_name") or f"도메인 {index + 1}")
        if name in seen:
            continue
        seen.add(name)
        source_ids = item.get("source_requirement_ids") or item.get("source_req_ids") or []
        groups.append(
            {
                **item,
                "domain_id": str(item.get("domain_id") or f"DOMAIN-{len(groups) + 1:03d}"),
                "domain_name": name,
                "source_requirement_ids": [str(value) for value in source_ids] if isinstance(source_ids, list) else [str(source_ids)],
                "description": _short_text(item.get("description") or item.get("detail_text") or name, 120),
            }
        )
    return groups


def _normalize_entities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entities = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        name = str(item.get("logical_name") or item.get("entity_name") or item.get("name") or f"엔티티 {index + 1}")
        if name in seen:
            continue
        seen.add(name)
        source_ids = item.get("source_requirement_ids") or item.get("source_req_ids") or []
        entities.append(
            {
                **item,
                "entity_id": str(item.get("entity_id") or f"ENT-{len(entities) + 1:03d}"),
                "logical_name": name,
                "description": _short_text(item.get("description") or name, 120),
                "source_requirement_ids": [str(value) for value in source_ids] if isinstance(source_ids, list) else [str(source_ids)],
            }
        )
    return entities


def _normalize_db_table(item: dict[str, Any], index: int) -> dict[str, Any]:
    table_name = str(item.get("table_name") or item.get("physical_name") or f"table_{index + 1}")
    columns = item.get("columns") if isinstance(item.get("columns"), list) else []
    normalized_columns = []
    for column_index, column in enumerate(columns):
        if not isinstance(column, dict):
            continue
        normalized_columns.append(
            {
                **column,
                "column_name": str(column.get("column_name") or column.get("physical_name") or f"column_{column_index + 1}"),
                "data_type": str(column.get("data_type") or "VARCHAR(255)"),
                "nullable": column.get("nullable", True),
                "default": column.get("default"),
                "description": str(column.get("description") or column.get("logical_name") or ""),
            }
        )
    if not normalized_columns:
        normalized_columns = [
            {
                "column_name": f"{table_name.removeprefix('tbl_')}_sn",
                "data_type": "BIGINT",
                "nullable": False,
                "default": None,
                "description": "기본키",
            }
        ]
    return {
        **item,
        "table_name": table_name,
        "table_description": str(item.get("table_description") or item.get("description") or item.get("logical_name") or table_name),
        "columns": normalized_columns,
        "constraints": item.get("constraints") if isinstance(item.get("constraints"), list) else _db_constraints(normalized_columns),
        "indexes": item.get("indexes") if isinstance(item.get("indexes"), list) else [],
    }


def _db_constraints(columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pk_columns = [
        column["column_name"]
        for column in columns
        if "PK" in column.get("constraints", []) or column["column_name"].endswith("_sn")
    ]
    return [{"type": "PK", "columns": [pk_columns[0]]}] if pk_columns else []


def _dedupe_results(results: list[Any]) -> list[dict[str, Any]]:
    deduped = []
    seen: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        score = float(result.get("score") or 0.0)
        if score and score < 0.2:
            continue
        key = str(result.get("citation") or result.get("content") or result)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _short_text(value: Any, max_length: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text if len(text) <= max_length else text[:max_length].rstrip()


def _normalize_relationship_names(
    relationships: list[Any],
    tables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not relationships:
        return []
    table_names = {table["physical_name"] for table in tables}
    table_by_logical = {str(table.get("logical_name")): table["physical_name"] for table in tables}

    normalized: list[dict[str, Any]] = []
    for index, relationship in enumerate(relationships):
        if not isinstance(relationship, dict):
            continue
        parent = _normalize_relation_table_name(
            str(relationship.get("parent_table") or relationship.get("source") or ""),
            table_names,
            table_by_logical,
        )
        child = _normalize_relation_table_name(
            str(relationship.get("child_table") or relationship.get("target") or ""),
            table_names,
            table_by_logical,
        )
        if parent not in table_names or child not in table_names:
            continue
        normalized.append(
            {
                **relationship,
                "relationship_id": str(relationship.get("relationship_id") or f"REL-{index + 1:03d}"),
                "parent_table": parent,
                "child_table": child,
            }
        )
    return normalized


def _normalize_relation_table_name(
    value: str,
    table_names: set[str],
    table_by_logical: dict[str, str],
) -> str:
    if value in table_names:
        return value
    if value in table_by_logical:
        return table_by_logical[value]
    candidate = table_name(value)
    if candidate in table_names:
        return candidate
    return value
