from collections.abc import Callable
from typing import Any

from tools.result import ToolResult, error_result, success_result


RuleParser = Callable[[str], Any]


def parse_rfp_requirements(
    file_path: str,
    *,
    parser: RuleParser | None = None,
) -> ToolResult:
    """기존 RFP Rule Parser를 공통 Tool 반환 형식으로 연결합니다."""

    selected_parser = parser or _load_legacy_parser()
    if selected_parser is None:
        return error_result(
            "RFP_RULE_PARSER_NOT_IMPLEMENTED",
            "연결 가능한 기존 RFP Rule Parser가 없습니다.",
            {"file_path": file_path},
        )

    try:
        requirements = selected_parser(file_path)
        return success_result(
            {"file_path": file_path, "requirements": requirements}
        )
    except Exception as exc:
        return error_result("RFP_RULE_PARSE_FAILED", str(exc), {"file_path": file_path})


def _load_legacy_parser() -> RuleParser | None:
    try:
        from old.data_pipeline.parsers.rfp_requirement_extractor import (
            extract_requirements_from_rfp_docx,
        )

        return extract_requirements_from_rfp_docx
    except ImportError:
        # TODO: 레거시 Parser가 제거되면 신규 Rule Parser 구현으로 교체합니다.
        return None
