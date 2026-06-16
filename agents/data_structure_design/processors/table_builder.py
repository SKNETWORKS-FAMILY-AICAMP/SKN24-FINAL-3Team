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
        base_name = physical_name.removeprefix("tbl_")
        tables.append(
            {
                "table_id": f"TABLE-{index + 1:03d}",
                "entity_id": str(entity.get("entity_id") or f"ENT-{index + 1:03d}"),
                "logical_name": logical_name,
                "physical_name": physical_name,
                "description": _summary_text(entity.get("description") or f"{logical_name} 정보를 관리하는 엔티티입니다.", 80),
                "source_requirement_ids": entity.get("source_requirement_ids", []),
                "columns": [
                    {
                        "column_id": f"COL-{index + 1:03d}-001",
                        "logical_name": f"{logical_name} 일련번호",
                        "physical_name": pk_name,
                        "data_type": "BIGINT",
                        "nullable": False,
                        "constraints": ["PK"],
                        "description": f"{logical_name} 고유 식별자",
                    },
                    {
                        "column_id": f"COL-{index + 1:03d}-002",
                        "logical_name": f"{logical_name} 명",
                        "physical_name": f"{base_name}_nm",
                        "data_type": "VARCHAR(200)",
                        "nullable": False,
                        "constraints": [],
                        "description": f"{logical_name} 명칭",
                    },
                    {
                        "column_id": f"COL-{index + 1:03d}-003",
                        "logical_name": f"{logical_name} 내용",
                        "physical_name": f"{base_name}_cn",
                        "data_type": "TEXT",
                        "nullable": True,
                        "constraints": [],
                        "description": f"{logical_name} 상세 내용",
                    },
                    {
                        "column_id": f"COL-{index + 1:03d}-004",
                        "logical_name": f"{logical_name} 상태 코드",
                        "physical_name": f"{base_name}_stts_cd",
                        "data_type": "VARCHAR(20)",
                        "nullable": True,
                        "constraints": [],
                        "description": f"{logical_name} 처리 상태 코드",
                    },
                    {
                        "column_id": f"COL-{index + 1:03d}-005",
                        "logical_name": "사용 여부",
                        "physical_name": "use_yn",
                        "data_type": "CHAR(1)",
                        "nullable": False,
                        "constraints": [],
                        "description": "사용 여부",
                    },
                    {
                        "column_id": f"COL-{index + 1:03d}-006",
                        "logical_name": "등록 일시",
                        "physical_name": "reg_dt",
                        "data_type": "DATETIME",
                        "nullable": False,
                        "constraints": [],
                        "description": "데이터 등록 일시",
                    },
                    {
                        "column_id": f"COL-{index + 1:03d}-007",
                        "logical_name": "수정 일시",
                        "physical_name": "mdfcn_dt",
                        "data_type": "DATETIME",
                        "nullable": True,
                        "constraints": [],
                        "description": "데이터 수정 일시",
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
                "entity_id": str(item.get("entity_id") or f"ENT-{index + 1:03d}"),
                "logical_name": logical_name,
                "physical_name": physical_name,
                "description": _summary_text(item.get("description") or item.get("table_description") or logical_name, 80),
                "table_description": _summary_text(item.get("table_description") or item.get("description") or logical_name, 80),
                "columns": _ensure_minimum_columns(
                    [_normalize_erd_column(column, index, col_index, logical_name) for col_index, column in enumerate(columns)],
                    index,
                    logical_name,
                    physical_name,
                ),
            }
        )
    return _dedupe_table_and_column_names(_merge_duplicate_tables(raw_tables))


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
        "description": _summary_text(source.get("description") or logical_column_name, 60),
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
    if is_pk and not standardized.endswith(("_sn", "_id")):
        return primary_key_name(table_logical_name)
    return standardized.removeprefix("tbl_")


def _dedupe_table_and_column_names(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for table_index, table in enumerate(tables):
        table["table_id"] = str(table.get("table_id") or f"TABLE-{table_index + 1:03d}")
        table["entity_id"] = str(table.get("entity_id") or f"ENT-{table_index + 1:03d}")
        column_counts: dict[str, int] = {}
        unique_columns = []
        for column in table.get("columns", []):
            base_column = column["physical_name"]
            column_counts[base_column] = column_counts.get(base_column, 0) + 1
            if column_counts[base_column] == 1:
                unique_columns.append(column)
        table["columns"] = unique_columns
    return tables


def _short_text(value: Any, max_length: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text if len(text) <= max_length else text[:max_length].rstrip()


def _summary_text(value: Any, max_length: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    for marker in ("다.", ".", "요.", "임."):
        if marker in text:
            candidate = text.split(marker, 1)[0].strip() + marker
            return _short_text(candidate, max_length)
    return _short_text(text, max_length)


def _merge_duplicate_tables(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for table in tables:
        key = table["physical_name"]
        if key not in merged:
            merged[key] = table
            order.append(key)
            continue
        target = merged[key]
        target["source_requirement_ids"] = list(
            dict.fromkeys([*target.get("source_requirement_ids", []), *table.get("source_requirement_ids", [])])
        )
        target["columns"] = [*target.get("columns", []), *table.get("columns", [])]
        if len(str(table.get("description") or "")) > len(str(target.get("description") or "")):
            target["description"] = _summary_text(table.get("description"), 80)
            target["table_description"] = target["description"]
    return [merged[key] for key in order]


def _ensure_minimum_columns(
    columns: list[dict[str, Any]],
    table_index: int,
    logical_name: str,
    physical_name: str,
) -> list[dict[str, Any]]:
    base_name = physical_name.removeprefix("tbl_")
    existing = {column["physical_name"] for column in columns}
    required = [
        (f"{base_name}_nm", f"{logical_name} 명", "VARCHAR(200)", False, f"{logical_name} 명칭"),
        (f"{base_name}_cn", f"{logical_name} 내용", "TEXT", True, f"{logical_name} 상세 내용"),
        (f"{base_name}_stts_cd", f"{logical_name} 상태 코드", "VARCHAR(20)", True, f"{logical_name} 처리 상태 코드"),
        ("use_yn", "사용 여부", "CHAR(1)", False, "사용 여부"),
        ("reg_dt", "등록 일시", "DATETIME", False, "데이터 등록 일시"),
        ("mdfcn_dt", "수정 일시", "DATETIME", True, "데이터 수정 일시"),
    ]
    for physical, logical, data_type, nullable, description in required:
        if len(columns) >= 6:
            break
        if physical in existing:
            continue
        existing.add(physical)
        columns.append(
            {
                "column_id": f"COL-{table_index + 1:03d}-{len(columns) + 1:03d}",
                "logical_name": logical,
                "physical_name": physical,
                "data_type": data_type,
                "nullable": nullable,
                "constraints": [],
                "description": description,
            }
        )
    return columns


def _constraints(table: dict[str, Any]) -> list[dict[str, Any]]:
    constraints = []
    for column in table.get("columns", []):
        if "PK" in column.get("constraints", []):
            constraints.append({"type": "PK", "columns": [column["physical_name"]]})
    return constraints
