# 추출된 엔티티를 기반으로 ERD 테이블과 DB 명세를 설계합니다.

from copy import deepcopy
import re
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
                "description": _table_description(logical_name),
                "table_description": _table_description(logical_name),
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
                "description": _table_description(logical_name),
                "table_description": _table_description(logical_name),
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
        "constraints": _normalize_column_constraints(source.get("constraints"), source.get("constraint"), is_first),
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


def _table_description(logical_name: Any) -> str:
    subject = _description_subject(logical_name)
    if not subject:
        subject = "업무"
    if subject.endswith("정보"):
        return f"{subject}를 관리하는 테이블입니다."
    if subject.endswith("관리"):
        return f"{subject} 업무 정보를 관리하는 테이블입니다."
    return f"{subject} 정보를 관리하는 테이블입니다."


def _description_subject(value: Any) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    text = re.sub(r"[\[\]{}()<>※★*#|`\"'·•:;]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_/.,")
    text = re.sub(r"(테이블|엔티티)$", "", text).strip()
    return _short_text(text, 40)


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
        target["description"] = _table_description(target.get("logical_name"))
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


def _normalize_column_constraints(raw_constraints: Any, raw_constraint: Any, is_pk: bool) -> list[str]:
    values: list[str] = ["PK"] if is_pk else []
    candidates: list[Any] = []
    if isinstance(raw_constraints, list):
        candidates.extend(raw_constraints)
    elif raw_constraints:
        candidates.append(raw_constraints)
    if raw_constraint:
        candidates.append(raw_constraint)
    for candidate in candidates:
        text = str(candidate).strip()
        if not text:
            continue
        upper = text.upper()
        if upper in {"PK", "PRIMARY KEY"}:
            if "PK" not in values:
                values.append("PK")
            continue
        if upper in {"FK", "FOREIGN KEY"}:
            if "FK" not in values:
                values.append("FK")
            continue
        if _looks_like_business_constraint(text):
            values.append(text)
    return list(dict.fromkeys(values))


def _looks_like_business_constraint(text: str) -> bool:
    keywords = {
        "마스킹",
        "암호",
        "해시",
        "권한",
        "접근",
        "보관",
        "파기",
        "개인정보",
        "필수",
        "유일",
        "중복",
        "최소",
        "최대",
        "이내",
        "초",
        "분",
        "허용",
        "금지",
        "검증",
        "제한",
        "정책",
        "감사",
        "로그",
        "백업",
    }
    return any(keyword in text for keyword in keywords)
