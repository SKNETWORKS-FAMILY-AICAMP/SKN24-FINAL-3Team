"""비기능 요구사항 Vector 저장 진입점입니다."""

from typing import Any

from tools.result import ToolResult, success_result


def write_non_functional_requirements(
    requirements: list[dict[str, Any]],
    *,
    project_sn: int | None = None,
    source_path: str | None = None,
    writer: Any | None = None,
) -> ToolResult:
    """비기능/제약 요구사항을 Vector DB에 저장합니다.

    실제 Qdrant/Embedding 연동 전에는 writer 주입 시에만 호출하고,
    기본값은 저장 대상 개수만 반환하는 no-op 구조입니다.
    """

    targets = [
        item
        for item in requirements
        if isinstance(item, dict) and not _is_functional_requirement(item)
    ]
    if writer is not None:
        writer(targets, project_sn=project_sn, source_path=source_path)
    return success_result({"stored_count": len(targets)})


def _is_functional_requirement(item: dict[str, Any]) -> bool:
    requirement_type = str(item.get("requirement_type") or item.get("type") or "").strip().lower()
    return requirement_type in {"기능", "기능 요구사항", "functional", "function"}
