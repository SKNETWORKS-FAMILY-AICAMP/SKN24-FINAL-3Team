import re
from pathlib import Path
from typing import Iterable

import fitz


def clean_text(text: str) -> str:
    """PDF 추출 텍스트의 노이즈 제거."""
    # 특수문자 반복 라인 제거 (구분선 등)
    text = re.sub(r"[─═━\-=\*\.]{4,}", "", text)

    # 3자 이하 단독 줄 제거 (페이지 번호, 머리글/바닥글)
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if len(stripped) > 3 or stripped == "":
            lines.append(line)
    text = "\n".join(lines)

    # 다중 공백 정리
    text = re.sub(r"[ \t]{4,}", " ", text)
    # 연속 빈 줄 압축
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def read_pdf_pages(
    path: Path,
    *,
    page_filter=None,  # callable: (page_num: int) -> bool
) -> Iterable[tuple[int, str]]:
    """
    PDF를 페이지 단위로 읽어서 (페이지번호, 정제된 텍스트) 튜플을 yield.

    page_filter가 주어지면 해당 조건을 만족하는 페이지만 처리.
    """
    doc = fitz.open(path)
    try:
        for page_num, page in enumerate(doc, start=1):
            if page_filter and not page_filter(page_num):
                continue
            text = page.get_text()
            if not text.strip():
                continue
            yield page_num, clean_text(text)
    finally:
        doc.close()