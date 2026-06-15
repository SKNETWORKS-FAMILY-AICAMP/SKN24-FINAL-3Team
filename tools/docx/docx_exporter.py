"""final_document_json payload를 템플릿 DOCX 양식에 맞춰 생성합니다."""

import copy
import json
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Inches, Pt
from docx.table import Table

from tools.result import ToolResult, error_result, success_result


def export_docx(
    export_payload: dict[str, Any],
    output_path: str,
    *,
    template_path: str | None = None,
) -> ToolResult:
    """유효한 템플릿이 있으면 산출물별 표 구조를 채우고, 없으면 기본 문서를 생성합니다."""

    try:
        target = Path(output_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        template = Path(template_path).resolve() if template_path else None
        document = (
            Document(str(template))
            if template and template.is_file() and zipfile.is_zipfile(template)
            else Document()
        )

        if template and template.is_file() and zipfile.is_zipfile(template):
            _fill_template_document(document, export_payload)
        else:
            _fill_generic_document(document, export_payload)

        document.save(target)
        return success_result(
            {
                "local_file_path": str(target),
                "file_name": target.name,
                "file_size": target.stat().st_size,
            }
        )
    except Exception as exc:
        return error_result("DOCX_EXPORT_FAILED", str(exc))


def _fill_template_document(document: Any, payload: dict[str, Any]) -> None:
    docs_cd = str(payload.get("docs_cd") or "").upper()
    if docs_cd == "SRS":
        _fill_srs_template(document, _list_content(payload, "requirement_json_list"))
    elif docs_cd == "INTERFACE":
        _fill_interface_template(
            document,
            _list_content(payload, "interface_json_list"),
            _list_content(payload, "ui_structure"),
        )
    elif docs_cd == "ERD":
        _fill_erd_template(
            document,
            _dict_content(payload, "erd_entity_json"),
            _first_image_path(payload),
        )
    elif docs_cd == "DB":
        _fill_db_template(document, _dict_content(payload, "db_design_json"))
    elif docs_cd == "ARCH":
        _fill_arch_template(
            document,
            _dict_content(payload, "architecture_document_json"),
            _first_image_path(payload),
        )
    else:
        _fill_generic_document(document, payload)


def _fill_generic_document(document: Any, export_payload: dict[str, Any]) -> None:
    document.add_heading(str(export_payload.get("title", "산출물")), level=0)
    for section_name, section_value in export_payload.get("content", {}).items():
        document.add_heading(section_name, level=1)
        _append_value(document, section_value)

    for image_path in export_payload.get("image_paths", []):
        image = Path(str(image_path))
        if image.is_file():
            document.add_picture(str(image), width=Inches(6.0))


def _fill_srs_template(document: Any, requirements: list[dict[str, Any]]) -> None:
    if len(document.tables) < 2:
        _fill_generic_document(document, {"title": "요구사항 정의서", "content": {"requirement_json_list": requirements}})
        return

    header = document.tables[0]
    _set_cell_safe(header, 2, 3, str(date.today()))
    _set_cell_safe(header, 2, 5, "v1.0")

    table = document.tables[1]
    base_row_idx = 1
    for index, requirement in enumerate(requirements):
        row = table.rows[base_row_idx + index] if base_row_idx + index < len(table.rows) else table.add_row()
        values = [
            _pick(requirement, "requirement_id", "req_id", "id"),
            _pick(requirement, "requirement_name", "req_name", "name"),
            _pick(requirement, "requirement_type", "type"),
            _pick(requirement, "description", "detail_text", "content"),
            _join(_pick(requirement, "source", "source_req_ids", "source_refs")),
            _join(requirement.get("constraints")),
            _pick(requirement, "priority", default="미지정"),
            _pick(requirement, "note"),
            _join(requirement.get("validation_criteria")),
            _pick(requirement, "status", default=""),
        ]
        for cell, value in zip(row.cells, values):
            _set_cell(cell, value)


def _fill_interface_template(
    document: Any,
    screens: list[dict[str, Any]],
    ui_structure: list[dict[str, Any]] | None = None,
) -> None:
    if len(document.tables) < 5:
        _fill_generic_document(document, {"title": "인터페이스 설계서", "content": {"interface_json_list": screens}})
        return

    _fill_interface_header(document.tables[0])
    _fill_interface_structure_table(document.tables[1], screens, ui_structure or [])
    _fill_repeating_table(
        document.tables[2],
        [[_pick(screen, "screen_id"), _pick(screen, "screen_name", "name")] for screen in screens],
    )

    detail_template = document.tables[3]
    process_template = document.tables[4]
    heading = _find_paragraph(document, "3.1")
    if not screens:
        _fill_interface_detail_table(detail_template, {})
        _fill_interface_process_table(process_template, [])
        return

    for index, screen in enumerate(screens, start=1):
        heading_text = _build_screen_heading(index, screen)
        if index == 1:
            if heading is not None:
                heading.text = ""
                run = heading.add_run(heading_text)
                run.bold = True
                run.font.size = Pt(10)
            detail_table = detail_template
            process_table = process_template
        else:
            anchor = process_template._tbl if index == 2 else process_table._tbl
            page_break = _insert_paragraph_after(document, anchor, page_break=True)
            heading = _insert_paragraph_after(document, page_break._p, heading_text)
            detail_table = _clone_table_after(heading._p, detail_template)
            blank = _insert_paragraph_after(document, detail_table._tbl)
            process_table = _clone_table_after(blank._p, process_template)

        _fill_interface_detail_table(detail_table, screen)
        _fill_interface_process_table(process_table, _process_contents(screen))


def _fill_erd_template(document: Any, erd: dict[str, Any], image_path: str | None) -> None:
    entities = _erd_entities(erd)
    relationships = _erd_relationships(erd)
    if len(document.tables) < 3:
        _fill_generic_document(document, {"title": "ERD 설계서", "content": {"erd_entity_json": erd}, "image_paths": [image_path] if image_path else []})
        return

    header = document.tables[0]
    _set_cell_safe(header, 1, 1, erd.get("system_name", ""))
    _set_cell_safe(header, 2, 1, erd.get("stage_name", "설계"))
    _set_cell_safe(header, 2, 4, erd.get("created_date", str(date.today())))
    _set_cell_safe(header, 2, 6, erd.get("version", "v1.0"))

    erd_table = document.tables[1]
    _set_cell_safe(erd_table, 0, 1, erd.get("erd_id", "ERD-SYSTEM-ALL"))
    _set_cell_safe(erd_table, 0, 3, erd.get("erd_name", "통합 ERD"))
    _set_cell_safe(erd_table, 1, 0, "")
    _insert_image_in_cell_safe(erd_table.cell(1, 0), image_path, width=6.5)

    template_table = document.tables[2]
    if not entities:
        _fill_erd_entity_table(template_table, {})
        return
    for _ in entities[1:]:
        _clone_table_after(template_table._tbl, template_table)
    for table, entity in zip(document.tables[2 : 2 + len(entities)], entities):
        _fill_erd_entity_table(table, entity)


def _fill_db_template(document: Any, design: dict[str, Any]) -> None:
    tables = _db_tables(design)
    if len(document.tables) < 4:
        _fill_generic_document(document, {"title": "DB 설계서", "content": {"db_design_json": design}})
        return

    header = document.tables[0]
    _set_cell_safe(header, 1, 1, design.get("system_name", ""))
    _set_cell_safe(header, 1, 4, design.get("subsystem_name", ""))
    _set_cell_safe(header, 2, 1, design.get("stage_name", "설계"))
    _set_cell_safe(header, 2, 4, design.get("created_date", str(date.today())))
    _set_cell_safe(header, 2, 6, design.get("version", "v1.0"))

    _fill_repeating_table(
        document.tables[1],
        [
            [
                design.get("database_id", "DB-001"),
                design.get("database_name", "업무 DB"),
                design.get("owner_department", ""),
                design.get("note", ""),
                "",
            ]
        ],
        base_row_idx=2,
    )

    definition = document.tables[2]
    _set_cell_safe(definition, 0, 1, design.get("database_id", "DB-001"))
    _set_cell_safe(definition, 0, 5, design.get("database_name", "업무 DB"))
    _set_cell_safe(definition, 1, 1, design.get("storage_group", ""))
    _set_cell_safe(definition, 1, 5, design.get("bufferpool", ""))
    _set_cell_safe(definition, 2, 1, design.get("index_bufferpool", ""))
    _fill_repeating_table(
        definition,
        [
            [
                _pick(table, "tablespace_name", default=""),
                _pick(table, "capacity", default="산정 필요"),
                _pick(table, "table_id", "table_name"),
                _pick(table, "table_name", "physical_name"),
                f"IX_{_pick(table, 'table_name', 'physical_name')}",
                "산정 필요",
                _pick(table, "note"),
            ]
            for table in tables
        ],
        base_row_idx=3,
    )

    template_table = document.tables[3]
    if not tables:
        _fill_db_table_spec(template_table, {})
        return
    for _ in tables[1:]:
        _clone_table_after(template_table._tbl, template_table)
    for table, item in zip(document.tables[3 : 3 + len(tables)], tables):
        _fill_db_table_spec(table, item)


def _fill_arch_template(document: Any, arch_doc: dict[str, Any], image_path: str | None) -> None:
    if len(document.tables) < 3:
        _fill_generic_document(document, {"title": "아키텍처 설계서", "content": {"architecture_document_json": arch_doc}, "image_paths": [image_path] if image_path else []})
        return

    header = document.tables[0]
    _set_cell_safe(header, 1, 1, _pick(arch_doc, "system_name", "project_name"))
    _set_cell_safe(header, 1, 4, _pick(arch_doc, "subsystem_name"))
    _set_cell_safe(header, 2, 1, _pick(arch_doc, "stage_name", default="설계"))
    _set_cell_safe(header, 2, 4, _pick(arch_doc, "created_date", default=str(date.today())))
    _set_cell_safe(header, 2, 6, _pick(arch_doc, "version", default="v1.0"))

    _insert_image_in_cell_safe(document.tables[1].cell(0, 0), image_path, width=6.2)

    requirements = _arch_requirement_items(arch_doc)
    template_table = document.tables[2]
    if not requirements:
        _fill_arch_requirement_table(template_table, {}, arch_doc)
        return
    for _ in requirements[1:]:
        _clone_table_after(template_table._tbl, template_table)
    for table, requirement in zip(document.tables[2 : 2 + len(requirements)], requirements):
        _fill_arch_requirement_table(table, requirement, arch_doc)


def _fill_interface_header(table: Table) -> None:
    _set_cell_safe(table, 2, 3, str(date.today()))
    _set_cell_safe(table, 2, 5, "v1.0")


def _fill_interface_structure_table(
    table: Table,
    screens: list[dict[str, Any]],
    ui_structure: list[dict[str, Any]] | None = None,
) -> None:
    rows = []
    for item in ui_structure or []:
        rows.append(
            [
                _pick(item, "level1"),
                _pick(item, "level2"),
                _pick(item, "level3"),
                _pick(item, "level4"),
            ]
        )
    if rows:
        _fill_repeating_table(table, rows)
        return
    for screen in screens:
        menu_path = str(_pick(screen, "menu_path", default=""))
        levels = [part.strip() for part in menu_path.split(">") if part.strip()]
        rows.append(
            [
                levels[0] if len(levels) > 0 else _pick(screen, "screen_name", "name"),
                levels[1] if len(levels) > 1 else "",
                levels[2] if len(levels) > 2 else "",
                levels[3] if len(levels) > 3 else "",
            ]
        )
    _fill_repeating_table(table, rows)


def _fill_interface_detail_table(table: Table, screen: dict[str, Any]) -> None:
    _set_cell_safe(table, 0, 0, "화면ID")
    _set_cell_safe(table, 0, 1, _pick(screen, "screen_id"))
    _set_cell_safe(table, 0, 2, "화면명")
    _set_cell_safe(table, 0, 3, _pick(screen, "screen_name", "name"))
    _set_cell_safe(table, 1, 0, "화면유형")
    _set_cell_safe(table, 1, 1, _pick(screen, "screen_type", default=""))
    _set_cell_safe(table, 1, 2, "메뉴경로")
    _set_cell_safe(table, 1, 3, _pick(screen, "menu_path", default=""))
    _set_cell_safe(table, 2, 0, "화면개요")
    _set_cell_safe(table, 2, 1, _pick(screen, "screen_overview", "description"))
    image_path = _pick(screen, "annotated_image_path", "image_path")
    if image_path:
        _insert_image_in_cell_safe(table.cell(3, 0), str(image_path), width=6.7)


def _fill_interface_process_table(table: Table, items: list[dict[str, Any]]) -> None:
    _set_cell_safe(table, 0, 0, "처리 내용")
    body = table.cell(1, 0)
    body.text = ""
    if not items:
        body.paragraphs[0].add_run("- 처리 내용 없음")
        return
    first = True
    for index, item in enumerate(items, start=1):
        paragraph = body.paragraphs[0] if first else body.add_paragraph()
        first = False
        no = _pick(item, "no", default=index)
        title = _pick(item, "title", "name", default=f"처리 {no}")
        paragraph.add_run(f"- {no}. {title}").bold = True
        description = _pick(item, "description", "content")
        basis = _pick(item, "requirement_basis", "basis")
        if description:
            body.add_paragraph(f"  · [{no}] {description}")
        if basis:
            body.add_paragraph(f"  · 근거: {basis}")


def _fill_erd_entity_table(table: Table, entity: dict[str, Any]) -> None:
    _set_cell_safe(table, 0, 2, _pick(entity, "entity_id", "table_id", default=""))
    _set_cell_safe(table, 0, 7, _pick(entity, "entity_name", "logical_name", "physical_name", "table_name"))
    _set_cell_safe(table, 1, 4, _pick(entity, "entity_description", "table_comment", "description"))
    rows = [_erd_column_to_row(column) for column in _entity_columns(entity)]
    _fill_repeating_table(table, rows, base_row_idx=3)


def _fill_db_table_spec(table: Table, item: dict[str, Any]) -> None:
    table_name = _pick(item, "table_name", "physical_name")
    _set_cell_safe(table, 0, 1, _pick(item, "table_id", default=table_name))
    _set_cell_safe(table, 0, 5, table_name)
    _set_cell_safe(table, 1, 1, _pick(item, "database_name", default="업무 DB"))
    _set_cell_safe(table, 1, 5, _pick(item, "tablespace_name", default=""))
    _set_cell_safe(table, 2, 1, _pick(item, "trigger_config", default=""))
    _set_cell_safe(table, 3, 1, _pick(item, "table_description", "description", "table_comment"))
    _fill_repeating_table(
        table,
        [
            [
                _pick(item, "initial_count", default=""),
                _pick(item, "daily_growth", default=""),
                _pick(item, "retention_period", default=""),
                _pick(item, "max_count", default=""),
                _pick(item, "capacity", default=""),
                _pick(item, "note", default=""),
            ]
        ],
        base_row_idx=5,
    )
    _fill_repeating_table(
        table,
        [_db_column_to_row(column) for column in _entity_columns(item)],
        base_row_idx=7,
    )


def _fill_arch_requirement_table(table: Table, requirement: dict[str, Any], arch_doc: dict[str, Any]) -> None:
    _set_cell_safe(table, 0, 1, _pick(requirement, "requirement_id", "req_id", "id"))
    _set_cell_safe(table, 2, 0, _pick(requirement, "description", "detail_text", "content"))
    _set_cell_safe(table, 4, 0, _arch_implementation_text(requirement, arch_doc))


def _append_value(document: Any, value: Any) -> None:
    if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
        keys = list(dict.fromkeys(key for item in value for key in item))
        table = document.add_table(rows=1, cols=len(keys))
        for index, key in enumerate(keys):
            table.rows[0].cells[index].text = str(key)
        for item in value:
            cells = table.add_row().cells
            for index, key in enumerate(keys):
                cells[index].text = _to_text(item.get(key))
        return
    document.add_paragraph(_to_text(value))


def _fill_repeating_table(table: Table, rows: list[list[Any]], base_row_idx: int = 1) -> None:
    for row_idx, values in enumerate(rows):
        row = table.rows[base_row_idx + row_idx] if base_row_idx + row_idx < len(table.rows) else table.add_row()
        for cell, value in zip(row.cells, values):
            _set_cell(cell, value)


def _set_cell_safe(table: Table, row_idx: int, col_idx: int, value: Any) -> None:
    if row_idx < len(table.rows) and col_idx < len(table.rows[row_idx].cells):
        _set_cell(table.cell(row_idx, col_idx), value)


def _set_cell(cell: Any, value: Any) -> None:
    cell.text = _to_plain_text(value)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(0)
        for run in paragraph.runs:
            run.font.size = Pt(8)


def _insert_image_in_cell_safe(
    cell: Any,
    image_path: str | None,
    *,
    width: float,
    trailing_text: str = "",
) -> None:
    image = Path(str(image_path)) if image_path else None
    if not image or not image.is_file():
        return
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(str(image), width=Inches(width))
    if trailing_text.strip():
        cell.add_paragraph(trailing_text)


def _clone_table_after(block: Any, table: Table) -> Table:
    new_tbl = copy.deepcopy(table._tbl)
    block.addnext(new_tbl)
    return Table(new_tbl, table._parent)


def _insert_paragraph_after(document: Any, block: Any, text: str = "", page_break: bool = False) -> Any:
    paragraph = document.add_paragraph()
    paragraph._p.getparent().remove(paragraph._p)
    block.addnext(paragraph._p)
    if page_break:
        paragraph.add_run().add_break(WD_BREAK.PAGE)
    if text:
        run = paragraph.add_run(text)
        run.bold = True
        run.font.size = Pt(10)
    return paragraph


def _find_paragraph(document: Any, prefix: str) -> Any | None:
    for paragraph in document.paragraphs:
        if paragraph.text.strip().startswith(prefix):
            return paragraph
    return None


def _list_content(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get("content", {}).get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dict_content(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get("content", {}).get(key)
    return value if isinstance(value, dict) else {}


def _first_image_path(payload: dict[str, Any]) -> str | None:
    images = payload.get("image_paths") or []
    return str(images[0]) if images else None


def _pick(data: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _join(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(_to_plain_text(item) for item in value)
    return _to_plain_text(value)


def _to_plain_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(_to_plain_text(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _to_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return "" if value is None else str(value)


def _process_contents(screen: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("process_contents", "actions", "user_actions"):
        value = screen.get(key)
        if isinstance(value, list):
            return [item if isinstance(item, dict) else {"description": item} for item in value]
    description = _pick(screen, "description")
    return [{"title": "화면 설명", "description": description}] if description else []


def _build_screen_heading(index: int, screen: dict[str, Any]) -> str:
    screen_id = str(_pick(screen, "screen_id", default=f"UI-{index:03d}"))
    suffix = screen_id.split("-")[-1]
    no = int(suffix) if suffix.isdigit() else index
    return f"3.{no} {_pick(screen, 'screen_name', 'name')}".strip()


def _erd_entities(erd: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(erd.get("entities"), list):
        return [item for item in erd["entities"] if isinstance(item, dict)]
    entities = []
    for index, table in enumerate(_db_tables(erd), start=1):
        entities.append(
            {
                "entity_id": _pick(table, "entity_id", "table_id", default=f"ENT-{index:03d}"),
                "entity_name": _entity_display_name(table),
                "entity_description": _short_text(_pick(table, "entity_description", "description", "table_comment"), 80),
                "columns": _entity_columns(table),
            }
        )
    return entities


def _erd_relationships(erd: dict[str, Any]) -> list[dict[str, Any]]:
    value = erd.get("relationships") or erd.get("relationship_list") or []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _relationship_text(item: dict[str, Any]) -> str:
    return (
        f"{_pick(item, 'from_entity', 'from_table')} "
        f"{_pick(item, 'relationship', 'type', default='1:N')} "
        f"{_pick(item, 'to_entity', 'to_table')} - "
        f"{_pick(item, 'description', 'from_column')}"
    ).strip(" -")


def _entity_columns(item: dict[str, Any]) -> list[dict[str, Any]]:
    value = item.get("columns") or item.get("column_list") or []
    return [column for column in value if isinstance(column, dict)] if isinstance(value, list) else []


def _erd_column_to_row(column: dict[str, Any]) -> list[Any]:
    return [
        _column_display_name(column),
        _short_text(_pick(column, "synonym", "logical_name", "description", "comment"), 30),
        _pick(column, "type", "data_type"),
        _pick(column, "length", default=""),
        _yes_no(not bool(column.get("nullable", True))) or _pick(column, "not_null"),
        _yes_no(column.get("is_pk")) or _pick(column, "pk"),
        _yes_no(column.get("is_fk")) or _pick(column, "fk"),
        _yes_no(column.get("is_pk") or column.get("is_fk")) or _pick(column, "inx"),
        _pick(column, "default", default=""),
        _short_text(_pick(column, "constraint", "constraints", "description", "comment"), 60),
    ]


def _entity_display_name(table: dict[str, Any]) -> str:
    explicit = _pick(table, "entity_name")
    if explicit:
        return _short_text(explicit, 40).upper()
    physical = _pick(table, "physical_name", "table_name")
    if physical:
        return str(physical).removeprefix("tbl_").upper()
    return _short_text(_pick(table, "logical_name"), 40).upper()


def _column_display_name(column: dict[str, Any]) -> str:
    physical = _pick(column, "physical_name", "column_name", "name")
    if physical:
        return str(physical).upper()
    return _short_text(_pick(column, "logical_name"), 40).upper()


def _short_text(value: Any, max_length: int) -> str:
    text = _to_plain_text(value).replace("\n", " ").strip()
    return text if len(text) <= max_length else text[: max_length - 1].rstrip() + "…"


def _db_tables(design: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("tables", "entities", "table_specification_json"):
        value = design.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _db_column_to_row(column: dict[str, Any]) -> list[Any]:
    constraints = column.get("constraints")
    return [
        _pick(column, "column_name", "physical_name", "name"),
        _pick(column, "column_id", "logical_name", "name"),
        _pick(column, "type_and_length", "data_type", "type"),
        _yes_no(not bool(column.get("nullable", True))) or _pick(column, "not_null"),
        _yes_no(column.get("is_pk")) or _contains_constraint(constraints, "PK"),
        _yes_no(column.get("is_fk")) or _contains_constraint(constraints, "FK"),
        _yes_no(column.get("is_pk") or column.get("is_fk")),
        _pick(column, "default", default=""),
        _pick(column, "constraint", "constraints", "description", "comment"),
    ]


def _yes_no(value: Any) -> str:
    if isinstance(value, str):
        return "Y" if value.upper() in {"Y", "YES", "TRUE", "PK", "FK"} else ""
    return "Y" if bool(value) else ""


def _contains_constraint(value: Any, needle: str) -> str:
    if isinstance(value, list):
        return "Y" if any(needle.upper() in str(item).upper() for item in value) else ""
    return "Y" if needle.upper() in str(value).upper() else ""


def _arch_requirement_items(arch_doc: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("requirements", "requirement_implementations", "drivers", "components"):
        value = arch_doc.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    overview = _pick(arch_doc, "overview")
    return [{"requirement_id": "ARCH-001", "description": overview}] if overview else []


def _arch_implementation_text(requirement: dict[str, Any], arch_doc: dict[str, Any]) -> str:
    direct = _pick(requirement, "implementation", "implementation_strategy", "description")
    components = arch_doc.get("components") or arch_doc.get("component_descriptions") or []
    relations = arch_doc.get("relations") or arch_doc.get("edges") or []
    parts = [direct] if direct else []
    if isinstance(components, list) and components:
        parts.append("구성요소: " + ", ".join(_pick(item, "name", "component_name", "id") for item in components if isinstance(item, dict)))
    if isinstance(relations, list) and relations:
        parts.append("관계: " + "; ".join(_relationship_text(item) for item in relations if isinstance(item, dict)))
    return "\n".join(part for part in parts if part)
