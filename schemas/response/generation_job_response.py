from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from schemas.common.common_schema import DocsCode


JobStatus = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCEL_REQUESTED",
    "CANCELED",
]


class GenerationJobError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class GenerationJobStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    project_sn: int
    docs_cd: DocsCode
    status: JobStatus
    step: str | None = None
    progress: int
    message: str | None = None
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: GenerationJobError | None = None
