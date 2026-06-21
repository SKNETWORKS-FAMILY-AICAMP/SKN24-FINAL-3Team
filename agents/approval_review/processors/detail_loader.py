from pathlib import Path
from typing import Any

from agents.approval_review.processors.json_loader import parse_content_text


def load_detail_content(detail: dict[str, Any]) -> dict[str, Any]:
    blob = detail.get("docs_dtl_cn")
    if blob not in (None, b"", ""):
        if isinstance(blob, memoryview):
            blob = blob.tobytes()
        if isinstance(blob, bytes):
            try:
                text = blob.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    f"docs_dtl_cn UTF-8 decode failed: {detail.get('docs_dtl_sn')}"
                ) from exc
        else:
            text = str(blob)
        return parse_content_text(text)

    docs_path = str(detail.get("docs_path") or "").strip()
    if not docs_path:
        raise ValueError(
            f"detail content and docs_path are empty: {detail.get('docs_dtl_sn')}"
        )
    try:
        text = Path(docs_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"docs_path read failed: {docs_path}") from exc
    return parse_content_text(text)
