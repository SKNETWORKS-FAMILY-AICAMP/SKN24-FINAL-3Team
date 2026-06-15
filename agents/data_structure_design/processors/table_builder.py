# 추출된 엔티티를 기반으로 ERD 테이블과 DB 명세를 설계합니다.

from copy import deepcopy
from typing import Any

from agents.data_structure_design.processors.column_standardizer import (
    primary_key_name,
    standardize_name,
    table_name,
)


def build_erd_tables(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables = []
    for index, entity in enumerate(entities):
        logical_name = str(entity["logical_name"])
        physical_name = table_name(logical_name)
        pk_name = primary_key_name(logical_name)
        tables.append(
            {
                "table_id": f"TABLE-{index + 1:03d}",
                "logical_name": logical_name,
                "physical_name": physical_name,
                "description": entity.get("description", ""),
                "source_requirement_ids": entity.get("source_requirement_ids", []),
                "columns": [
                    {
                        "column_id": f"COL-{index + 1:03d}-001",
                        "logical_name": f"{logical_name} 일련번호",
                        "physical_name": pk_name,
                        "data_type": "BIGINT",
                        "nullable": False,
                        "constraints": ["PK"],
                    },
                    {
                        "column_id": f"COL-{index + 1:03d}-002",
                        "logical_name": f"{logical_name} 명",
                        "physical_name": f"{physical_name.removeprefix('tbl_')}_nm",
                        "data_type": "VARCHAR(200)",
                        "nullable": False,
                        "constraints": [],
                    },
                ],
            }
        )
    return tables


def normalize_erd_tables(items: list[Any]) -> list[dict[str, Any]]:
    raw_tables = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        logical_name = str(item.get("logical_name") or item.get("table_description") or item.get("table_name") or f"테이블 {index + 1}")
        raw_physical_name = str(item.get("physical_name") or item.get("table_name") or "")
        physical_name = _standard_table_name(raw_physical_name, logical_name)
        columns = item.get("columns") if isinstance(item.get("columns"), list) else []
        if not columns:
            columns = build_erd_tables([{"logical_name": logical_name}])[0]["columns"]
        raw_tables.append(
            {
                **item,
                "table_id": str(item.get("table_id") or f"TABLE-{index + 1:03d}"),
                "logical_name": logical_name,
                "physical_name": physical_name,
                "columns": [_normalize_erd_column(column, index, col_index, logical_name) for col_index, column in enumerate(columns)],
            }
        )
    return _dedupe_table_and_column_names(raw_tables)


def build_db_design(tables: list[dict[str, Any]]) -> dict[str, Any]:
    db_tables = []
    for table in tables:
        db_tables.append(
            {
                "table_name": table["physical_name"],
                "table_description": table.get("description") or table["logical_name"],
                "columns": [
                    {
                        "column_name": column["physical_name"],
                        "data_type": column.get("data_type") or "VARCHAR(255)",
                        "nullable": column.get("nullable", True),
                        "default": column.get("default"),
                        "description": column.get("logical_name") or column["physical_name"],
                    }
                    for column in table.get("columns", [])
                ],
                "constraints": _constraints(table),
                "indexes": [],
            }
        )
    return {"tables": db_tables}


def normalize_db_design(items: list[Any]) -> dict[str, Any]:
    erd_tables = normalize_erd_tables(items)
    return build_db_design(erd_tables)


def _normalize_erd_column(column: Any, table_index: int, column_index: int, logical_name: str) -> dict[str, Any]:
    source = deepcopy(column) if isinstance(column, dict) else {}
    is_first = column_index == 0
    raw_name = str(source.get("physical_name") or source.get("column_name") or "")
    logical_column_name = str(source.get("logical_name") or source.get("description") or f"{logical_name} 컬럼")
    return {
        **source,
        "column_id": str(source.get("column_id") or f"COL-{table_index + 1:03d}-{column_index + 1:03d}"),
        "logical_name": logical_column_name,
        "physical_name": _standard_column_name(raw_name, logical_column_name, logical_name, is_first),
        "data_type": str(source.get("data_type") or "BIGINT"),
        "nullable": source.get("nullable", not is_first),
        "constraints": source.get("constraints") if isinstance(source.get("constraints"), list) else (["PK"] if is_first else []),
    }


def _standard_table_name(raw_name: str, logical_name: str) -> str:
    source = raw_name or table_name(logical_name)
    standardized = standardize_name(source, fallback="entity")
    if standardized == "tbl":
        standardized = standardize_name(logical_name, fallback="entity")
    return standardized if standardized.startswith("tbl_") else f"tbl_{standardized}"


def _standard_column_name(
    raw_name: str,
    logical_column_name: str,
    table_logical_name: str,
    is_pk: bool,
) -> str:
    if is_pk:
        candidate = raw_name or primary_key_name(table_logical_name)
    else:
        candidate = raw_name or logical_column_name
    standardized = standardize_name(candidate, fallback="column")
    if standardized in {"column", "tbl_column"} and is_pk:
        return primary_key_name(table_logical_name)
    return standardized.removeprefix("tbl_")


def _dedupe_table_and_column_names(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table_counts: dict[str, int] = {}
    for table in tables:
        base = table["physical_name"]
        table_counts[base] = table_counts.get(base, 0) + 1
        if table_counts[base] > 1:
            table["physical_name"] = f"{base}_{table_counts[base]}"

        column_counts: dict[str, int] = {}
        for column in table.get("columns", []):
            base_column = column["physical_name"]
            column_counts[base_column] = column_counts.get(base_column, 0) + 1
            if column_counts[base_column] > 1:
                column["physical_name"] = f"{base_column}_{column_counts[base_column]}"
    return tables


def _constraints(table: dict[str, Any]) -> list[dict[str, Any]]:
    constraints = []
    for column in table.get("columns", []):
        if "PK" in column.get("constraints", []):
            constraints.append({"type": "PK", "columns": [column["physical_name"]]})
    return constraints
