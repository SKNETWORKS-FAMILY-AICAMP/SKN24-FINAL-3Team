"""RFP DOCX 표에서 요구사항 항목을 추출하는 Rule Parser입니다."""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from docx import Document

from tools.result import ToolResult, error_result, success_result
from tools.parser.pdf_parser import parse_pdf


RuleParser = Callable[[str], Any]

ID_PATTERN = re.compile(r"^[A-Za-z]{2,5}[\-\u2013\u2014]\d{2,4}$")

DEFAULT_PREFIX_MAP = {
    "SFR": "기능",
    "FUR": "기능",
    "ECR": "시스템 장비구성",
    "NFR": "비기능",
    "PER": "성능",
    "SER": "보안",
    "SEC": "보안",
    "QUR": "품질",
    "TER": "테스트",
    "TST": "테스트",
    "DAR": "데이터",
    "DBR": "데이터",
    "CSR": "컨설팅",
    "PSR": "프로젝트 지원",
    "PMR": "프로젝트 관리",
    "COR": "제약사항",
    "INT": "인터페이스",
    "INR": "인터페이스",
    "SIR": "시스템 장비구성",
    "MPR": "유지보수",
}

FIELD_ALIASES = {
    "name": {
        "요구사항명",
        "요구사항 명",
        "요구사항 명칭",
        "기능명",
        "기능 명",
        "항목명",
        "업무명",
    },
    "type": {"요구사항분류", "요구사항 구분", "구분", "분류", "유형"},
    "description": {"요구사항 상세설명", "상세설명", "상세 설명", "세부내용", "세부 내용", "정의"},
    "constraint": {"제약사항", "특이사항", "조건", "비고"},
    "validation": {"검증기준", "시험기준", "평가기준", "검수기준", "검토기준"},
    "priority": {"우선순위", "중요도"},
    "source_ref": {"관련 요구사항", "관련요구사항", "출처", "근거"},
}

BLACKLIST = {
    "요구사항명",
    "요구사항 명",
    "요구사항 명칭",
    "요구사항 고유번호",
    "요구사항 상세설명",
    "상세설명",
    "상세 설명",
    "세부내용",
    "세부 내용",
    "정의",
    "산출정보",
    "관련 요구사항",
    "관련요구사항",
    "검토기준",
    "검증기준",
    "비고",
    "구분",
    "분류",
    "유형",
    "사업수행계획서",
    "설계서",
    "결과보고서",
}


def parse_rfp_requirements(
    file_path: str,
    *,
    parser: RuleParser | None = None,
) -> ToolResult:
    """RFP 파일에서 요구사항 목록을 추출해 공통 ToolResult로 반환합니다."""

    selected_parser = parser or extract_requirements_from_rfp
    try:
        requirements = selected_parser(file_path)
        return success_result({"file_path": file_path, "requirements": requirements})
    except Exception as exc:
        return error_result("RFP_RULE_PARSE_FAILED", str(exc), {"file_path": file_path})


def extract_requirements_from_rfp(file_path: str) -> list[dict[str, Any]]:
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        return extract_requirements_from_rfp_pdf(file_path)
    return extract_requirements_from_rfp_docx(file_path)


def extract_requirements_from_rfp_docx(file_path: str) -> list[dict[str, Any]]:
    """DOCX 표를 순회하며 요구사항 ID 기준으로 항목을 구성합니다."""

    path = Path(file_path)
    document = Document(str(path))
    requirements_map: dict[str, dict[str, Any]] = {}

    for table_index, table in enumerate(document.tables):
        last_id: str | None = None
        for row_index, row in enumerate(table.rows):
            cells = _unique_cells(row.cells)
            if not cells:
                continue

            requirement_id = _find_requirement_id(cells)
            if requirement_id:
                last_id = requirement_id
                current = requirements_map.setdefault(
                    requirement_id,
                    _new_requirement(requirement_id, path.name, table_index, row_index),
                )
                current["desc_parts"].extend(
                    cell for cell in cells if _normalize_id(cell) != requirement_id
                )
                continue

            if not last_id:
                continue

            current = requirements_map[last_id]
            if len(cells) >= 2:
                field = _detect_field(cells[0])
                value = " ".join(cells[1:]).strip()
                if field == "name":
                    current["name"] = value
                    continue
                if field == "type":
                    current["type"] = value
                    continue
                if field == "description":
                    current["desc_parts"].append(value)
                    continue
                if field == "constraint":
                    current["constraints"].append(value)
                    continue
                if field == "validation":
                    current["validation_criteria"].append(value)
                    continue
                if field == "priority":
                    current["priority"] = value
                    continue
                if field == "source_ref":
                    current["source_refs"].append(value)
                    continue
                if "산출정보" in cells[0]:
                    continue

            current["desc_parts"].extend(cell for cell in cells if cell not in BLACKLIST)

    return [_build_requirement(data) for data in requirements_map.values() if _is_valid_requirement(data)]


def extract_requirements_from_rfp_pdf(file_path: str) -> list[dict[str, Any]]:
    """PDF 텍스트에서 요구사항 ID 블록을 찾아 요구사항 항목을 구성합니다."""

    parsed = parse_pdf(file_path)
    if not parsed["success"]:
        error = parsed["error"] or {}
        raise ValueError(str(error.get("message", "PDF 파싱에 실패했습니다.")))

    path = Path(file_path)
    requirements_map: dict[str, dict[str, Any]] = {}
    for page in parsed["data"].get("pages", []):
        page_number = int(page.get("page_number") or 0)
        lines = _pdf_lines(str(page.get("text") or ""))
        current_id: str | None = None
        line_index = 0
        while line_index < len(lines):
            line = lines[line_index]
            requirement_id = _find_requirement_id_in_text(line)
            if requirement_id:
                current_id = requirement_id
                current = requirements_map.setdefault(
                    requirement_id,
                    _new_requirement(requirement_id, path.name, page_number, line_index),
                )
                rest = _remove_requirement_id_label(line, requirement_id)
                if rest:
                    current["desc_parts"].append(rest)
                line_index += 1
                continue

            if not current_id:
                line_index += 1
                continue

            current = requirements_map[current_id]
            field_value = _split_pdf_field(line)
            if field_value:
                field, value = field_value
                _apply_pdf_field(current, field, value)
                line_index += 1
                continue

            field = _detect_field(line)
            if field:
                value, next_index = _collect_pdf_field_value(lines, line_index + 1, field)
                if value:
                    _apply_pdf_field(current, field, value)
                    line_index = next_index
                else:
                    line_index += 1
                continue

            if _looks_like_section_boundary(line):
                line_index += 1
                continue
            current["desc_parts"].append(line)
            line_index += 1

    return [_build_requirement(data) for data in requirements_map.values() if _is_valid_requirement(data)]


def _new_requirement(
    requirement_id: str,
    file_name: str,
    table_index: int,
    row_index: int,
) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "name": None,
        "type": None,
        "priority": None,
        "constraints": [],
        "validation_criteria": [],
        "source_refs": [],
        "desc_parts": [],
        "source": file_name,
        "table_index": table_index,
        "row_index": row_index,
    }


def _build_requirement(data: dict[str, Any]) -> dict[str, Any]:
    req_id = data["id"]
    unique_parts = _clean_parts(data["desc_parts"])
    name = data["name"] or _infer_requirement_name(unique_parts)
    description = _clean_description("\n".join(unique_parts))
    req_type = _normalize_requirement_type(
        req_id,
        data.get("type"),
        name,
        description,
    )
    source_refs = list(dict.fromkeys([*data["source_refs"], req_id]))
    validation_criteria = list(dict.fromkeys(data["validation_criteria"])) or ["검토 필요"]
    constraints = list(dict.fromkeys(data["constraints"]))

    return {
        "requirement_id": req_id,
        "requirement_name": name[:100],
        "requirement_type": req_type,
        "description": description,
        "source": [data["source"]],
        "constraints": constraints,
        "priority": data["priority"] or "미지정",
        "validation_criteria": validation_criteria,
        "note": None,
        "source_refs": source_refs,
        "metadata": {
            "source_file": data["source"],
            "table_index": data["table_index"],
            "row_index": data["row_index"],
        },
        "req_id": req_id,
        "req_name": name[:100],
        "detail_text": description,
        "source_req_ids": source_refs,
    }


def _unique_cells(cells: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for cell in cells:
        text = normalize_text(cell.text)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _find_requirement_id(cells: list[str]) -> str | None:
    for cell in cells:
        normalized = _normalize_id(cell)
        if ID_PATTERN.match(normalized):
            return normalized
    return None


def _find_requirement_id_in_text(text: str) -> str | None:
    normalized = _normalize_id(text)
    match = re.search(r"\b[A-Z]{2,5}-\d{2,4}\b", normalized)
    return match.group(0) if match else None


def _normalize_id(text: str) -> str:
    return re.sub(r"[\-\u2013\u2014]", "-", text.strip()).upper()


def normalize_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _detect_field(text: str) -> str | None:
    normalized = normalize_text(text)
    for field, aliases in FIELD_ALIASES.items():
        if any(normalized == alias or alias in normalized for alias in aliases):
            return field
    return None


def _pdf_lines(text: str) -> list[str]:
    return [normalize_text(line) for line in text.splitlines() if normalize_text(line)]


def _remove_requirement_id_label(text: str, requirement_id: str) -> str:
    value = _normalize_id(text)
    value = value.replace(requirement_id, " ")
    value = re.sub(r"(요구사항\s*고유번호|요구사항\s*번호|요구사항\s*ID|ID)\s*[:：]?", " ", value, flags=re.IGNORECASE)
    return normalize_text(value)


def _split_pdf_field(text: str) -> tuple[str, str] | None:
    normalized = normalize_text(text)
    if any(normalized == alias for aliases in FIELD_ALIASES.values() for alias in aliases):
        return None
    for separator in (":", "："):
        if separator in normalized:
            label, value = [part.strip() for part in normalized.split(separator, 1)]
            field = _detect_field(label)
            if field and value:
                return field, value

    field = _detect_field(normalized)
    if not field:
        return None
    for aliases in FIELD_ALIASES.values():
        for alias in sorted(aliases, key=len, reverse=True):
            if normalized.startswith(alias):
                value = normalize_text(normalized[len(alias):])
                value = re.sub(r"^[\s\-:：]+", "", value)
                if value:
                    return field, value
    return None


def _collect_pdf_field_value(
    lines: list[str],
    start_index: int,
    field: str,
) -> tuple[str, int]:
    values: list[str] = []
    index = start_index
    while index < len(lines):
        line = lines[index]
        if _find_requirement_id_in_text(line):
            break
        if _detect_field(line):
            break
        if line in BLACKLIST or line in {"요구사항", "상세설명"}:
            index += 1
            if field in {"name", "type", "priority", "source_ref"} and values:
                break
            continue
        if _looks_like_section_boundary(line):
            if values:
                break
            index += 1
            continue
        values.append(line)
        index += 1
        if field in {"type", "priority", "source_ref", "validation", "constraint"}:
            break
        if field == "name" and len(values) >= 4:
            break
        if field == "description" and len(values) >= 20:
            break
    return _clean_pdf_field_value(field, values), index


def _clean_pdf_field_value(field: str, values: list[str]) -> str:
    if not values:
        return ""
    if field == "name":
        value = " ".join(values)
        value = re.sub(r"\s*([()])\s*", r"\1", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()
    return "\n".join(values).strip()


def _apply_pdf_field(current: dict[str, Any], field: str, value: str) -> None:
    if not value:
        return
    if field == "name":
        current["name"] = value
    elif field == "type":
        current["type"] = value
    elif field == "description":
        current["desc_parts"].append(value)
    elif field == "constraint":
        current["constraints"].append(value)
    elif field == "validation":
        current["validation_criteria"].append(value)
    elif field == "priority":
        current["priority"] = value
    elif field == "source_ref":
        current["source_refs"].append(value)


def _looks_like_section_boundary(text: str) -> bool:
    normalized = normalize_text(text)
    if normalized in BLACKLIST:
        return True
    return bool(re.match(r"^\d+(\.\d+){0,4}\s+.{1,30}$", normalized))


def _clean_parts(parts: list[str]) -> list[str]:
    unique_parts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = normalize_text(part)
        if not text or text in BLACKLIST or len(text) <= 2 or text in seen:
            continue
        seen.add(text)
        unique_parts.append(text)
    return unique_parts


def _clean_description(description: str) -> str:
    description = re.sub(
        r"(요구사항\s*고유번호|요구사항\s*상세설명|세부내용|정의)",
        "",
        description,
    )
    description = re.sub(r"\n{2,}", "\n", description)
    return description.strip()


def _is_valid_requirement(data: dict[str, Any]) -> bool:
    req_id = data["id"]
    if req_id.endswith("-000") or req_id.endswith("-00"):
        return False
    return len(_clean_description("\n".join(_clean_parts(data["desc_parts"])))) > 20


def _infer_requirement_name(parts: list[str]) -> str:
    for part in parts:
        text = normalize_text(part)
        if len(text) < 4 or text.isdigit() or text in BLACKLIST:
            continue
        if "요구사항" in text and len(text) < 20:
            continue
        return text[:100]
    return "미분류"


def _infer_requirement_type(req_id: str, name: str, description: str) -> str:
    name_text = normalize_text(name)
    if "보안" in name_text:
        return "보안"
    if "성능" in name_text:
        return "성능"
    if "품질" in name_text:
        return "품질"
    if "인터페이스" in name_text or "UI" in name_text.upper():
        return "인터페이스"
    if "데이터" in name_text:
        return "데이터"
    if "프로젝트 지원" in name_text:
        return "프로젝트 지원"
    if "지원" in name_text:
        return "프로젝트 지원"
    if "장비구성" in name_text or "인프라" in name_text:
        return "시스템 장비구성"

    prefix = req_id.split("-")[0].upper()
    if prefix in DEFAULT_PREFIX_MAP:
        return DEFAULT_PREFIX_MAP[prefix]

    text = f"{name} {description[:500]}".lower()
    if any(keyword in text for keyword in ("보안", "암호화", "접근제어", "접근 통제", "개인정보")):
        return "보안"
    if any(keyword in text for keyword in ("처리량", "응답속도", "동시접속", "throughput")):
        return "성능"
    if any(keyword in text for keyword in ("인프라", "서버", "아키텍처")):
        return "시스템 장비구성"
    return "기능"


def _normalize_requirement_type(
    req_id: str,
    raw_type: Any,
    name: str,
    description: str,
) -> str:
    prefix = req_id.split("-")[0].upper()
    inferred = _infer_requirement_type(req_id, name, description)
    if prefix in DEFAULT_PREFIX_MAP:
        default = DEFAULT_PREFIX_MAP[prefix]
    else:
        default = inferred
    if prefix in {"SFR", "FUR"}:
        return "기능"

    value = normalize_text(str(raw_type or ""))
    if not value:
        return default
    if value in {"기능", "기능 요구사항"}:
        return "기능"
    if value in {"비기능", "비기능 요구사항"}:
        return "비기능"
    if any(keyword in value for keyword in ("보안", "성능", "품질", "데이터", "인터페이스")):
        return _infer_requirement_type(req_id, value, description)
    if "시스템" in value or "장비" in value or "인프라" in value:
        return "시스템 장비구성"
    if len(value) > 20 or value.startswith(("ㅇ", "-", ",")):
        return default
    return default if prefix in DEFAULT_PREFIX_MAP else value


def dump_requirements_json(requirements: list[dict[str, Any]]) -> str:
    """수동 검증과 CLI 출력에 쓰는 JSON 직렬화 helper입니다."""

    return json.dumps({"requirements": requirements}, ensure_ascii=False, indent=2)
