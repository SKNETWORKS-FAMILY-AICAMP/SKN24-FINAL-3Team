from typing import Any, Literal

from pydantic import BaseModel, Field


ReviewStatus = Literal["ok", "issues_found", "failed", "skipped"]


class ApprovalReviewRequest(BaseModel):
    docs_sn: int = Field(gt=0)
    approval_request_docs_dtl_sn: int = Field(gt=0)


class ApprovalReviewStartResponse(BaseModel):
    job_id: str
    status: Literal["processing"]


class ApprovalReviewJobResponse(BaseModel):
    job_id: str
    status: Literal["processing", "done", "failed"]
    result: dict[str, Any] | None = None
    error_message: str | None = None
