# ERD 구조를 Mermaid 코드로 생성합니다.

import re
from typing import Any


def build_erd_mermaid(structure: dict[str, Any]) -> str:
    entities = structure.get("entities") or structure.get("tables") or []
    relationships = structure.get("relationships") or structure.get("relations") or []
    lines = ["erDiagram"]
    for entity in entities:
        name = str(entity.get("name") or entity.get("physical_name") or entity.get("table_name") or "")
        if not name:
            continue
        table_name = _identifier(name)
        lines.append(f"    {table_name} {{")
        for column in entity.get("columns") or []:
            data_type = _data_type(str(column.get("data_type") or "VARCHAR"))
            column_name = _identifier(str(column.get("physical_name") or column.get("column_name") or "column"))
            constraints = column.get("constraints") or []
            marker = " PK" if "PK" in constraints else (" FK" if "FK" in constraints else "")
            lines.append(f"        {data_type} {column_name}{marker}")
        lines.append("    }")
    for relation in relationships:
        parent = relation.get("parent_table") or relation.get("from") or relation.get("source")
        child = relation.get("child_table") or relation.get("to") or relation.get("target")
        if parent and child:
            label = _label(str(relation.get("description") or relation.get("label") or "relates"))
            lines.append(f"    {_identifier(str(parent))} ||--o{{ {_identifier(str(child))} : {label}")
    return "\n".join(lines)


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]", "_", value).strip("_")
    if not normalized:
        return "item"
    if normalized[0].isdigit():
        return f"t_{normalized}"
    return normalized


def _data_type(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]", "_", value).strip("_").upper()
    return normalized or "VARCHAR"


def _label(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_ -]", "", value).strip() or "relates"
