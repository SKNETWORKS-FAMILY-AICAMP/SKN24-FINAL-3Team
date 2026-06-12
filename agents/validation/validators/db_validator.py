# DB 설계서의 테이블과 컬럼 구조를 검증합니다.

from typing import Any

from agents.validation.schemas import first_list, is_empty, make_check, missing_fields, missing_keys
from workflow.state import WorkflowState


TARGET = "data_structure_design_agent"


def validate(state: WorkflowState) -> list[dict[str, Any]]:
    document = state.get("agent_outputs", {}).get(TARGET, {}).get("db_design_json")
    tables = first_list(document, "tables", "table_json_list")
    checks = [
        make_check("DB_OUTPUT_001", "DB 설계 출력 존재 검증", not is_empty(document), failure_type="DB_OUTPUT_MISSING", message="db_design_json이 없습니다.", target_agent=TARGET)
    ]
    if not tables:
        checks.append(make_check("DB_SCHEMA_001", "DB 설계 Schema 검증", False, failure_type="DB_SCHEMA_ERROR", message="DB 테이블 목록이 없거나 구조가 올바르지 않습니다.", target_agent=TARGET))
        return checks

    table_missing, column_missing, type_missing, constraint_invalid, index_invalid = [], [], [], [], []
    for index, table in enumerate(tables):
        scope = str(table.get("table_name") or index) if isinstance(table, dict) else str(index)
        if not isinstance(table, dict) or missing_fields(table, ["table_name", "table_description", "columns"]) or missing_keys(table, ["constraints", "indexes"]):
            table_missing.append(scope)
            continue
        columns = table["columns"] if isinstance(table["columns"], list) else []
        if not columns or any(not isinstance(column, dict) or missing_fields(column, ["column_name", "data_type", "description"]) or missing_keys(column, ["nullable", "default"]) for column in columns):
            column_missing.append(scope)
        if any(is_empty(column.get("data_type")) for column in columns if isinstance(column, dict)):
            type_missing.append(scope)
        if not isinstance(table.get("constraints"), list):
            constraint_invalid.append(scope)
        if not isinstance(table.get("indexes"), list):
            index_invalid.append(scope)
    checks.extend(
        [
            make_check("DB_SCHEMA_001", "DB 테이블 필수 필드 검증", not table_missing, failure_type="DB_SCHEMA_ERROR", message="테이블 필수 필드가 누락되었습니다.", target_agent=TARGET, target_scope=table_missing),
            make_check("DB_COLUMN_001", "DB 컬럼 검증", not column_missing, failure_type="DB_COLUMN_MISSING", message="컬럼 또는 컬럼 필수 필드가 누락되었습니다.", target_agent=TARGET, target_scope=column_missing),
            make_check("DB_TYPE_001", "데이터 타입 검증", not type_missing, failure_type="DB_DATA_TYPE_MISSING", message="데이터 타입이 누락된 컬럼이 있습니다.", target_agent=TARGET, target_scope=type_missing),
            make_check("DB_CONSTRAINT_001", "제약조건 구조 검증", not constraint_invalid, failure_type="DB_CONSTRAINT_INVALID", message="제약조건 구조가 올바르지 않습니다.", target_agent=TARGET, target_scope=constraint_invalid),
            make_check("DB_INDEX_001", "인덱스 구조 검증", not index_invalid, failure_type="DB_INDEX_INVALID", message="인덱스 구조가 올바르지 않습니다.", target_agent=TARGET, target_scope=index_invalid, severity="MEDIUM"),
        ]
    )
    return checks
