import json
from typing import Any

from agents.approval_review.prompts import IMPACT_SYSTEM_PROMPT
from tools.llm.llm_client import LLMClient
from tools.llm.response_parser import parse_json_response


ALLOWED_ARTIFACTS = {"SRS", "UI", "ARCH", "ERD", "DB", "TS"}


def classify_impacts(
    changes: list[dict[str, Any]], llm_client: LLMClient | None = None
) -> list[dict[str, Any]]:
    if not changes:
        return []
    client = llm_client or LLMClient()
    payload = [
        {
            "index": index,
            "change_type": item["change_type"],
            "target_path": item["target_path"],
            "title": item["title"],
            "before": item["before"],
            "after": item["after"],
        }
        for index, item in enumerate(changes)
    ]
    response = client.chat(
        [
            {"role": "system", "content": IMPACT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"changes": payload}, ensure_ascii=False, default=str),
            },
        ],
        temperature=0,
    )
    parsed = parse_json_response(response["data"]) if response["success"] else None
    classifications = (
        parsed["data"].get("classifications", [])
        if parsed and parsed["success"] and isinstance(parsed["data"], dict)
        else []
    )
    by_index = {
        item.get("index"): item
        for item in classifications
        if isinstance(item, dict) and isinstance(item.get("index"), int)
    }

    results: list[dict[str, Any]] = []
    for index, change in enumerate(changes):
        classification = by_index.get(index, {})
        artifacts = [
            str(value).upper()
            for value in classification.get("affected_artifacts", [])
            if str(value).upper() in ALLOWED_ARTIFACTS
        ]
        reason = str(classification.get("reason") or "").strip()
        message = str(classification.get("message") or "").strip()
        if not message:
            message = (
                f"{change['title']} 항목이 {change['change_type']}되었습니다."
                + (
                    f" {', '.join(artifacts)} 산출물 확인이 필요합니다."
                    if artifacts
                    else " 관련 산출물 영향도를 확인해 주세요."
                )
            )
        results.append(
            {
                **change,
                "affected_artifacts": list(dict.fromkeys(artifacts)),
                "reason": reason or "LLM 영향 분류 결과가 없어 PM 확인이 필요합니다.",
                "message": message,
            }
        )
    return results
