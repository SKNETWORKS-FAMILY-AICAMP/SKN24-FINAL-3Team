from datetime import datetime
from itertools import count
from threading import Lock

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.approval_review.agent import ApprovalReviewAgent
from agents.approval_review.repository import ApprovalReviewRepository
from agents.approval_review.schemas import (
    ApprovalReviewJobResponse,
    ApprovalReviewRequest,
    ApprovalReviewStartResponse,
)
from config.logging_config import get_logger
from database.session import SessionLocal, get_db_session


router = APIRouter(prefix="/approval/artifacts/review", tags=["approval-review"])
logger = get_logger("api.approval_review_router")
_sequence = count(1)
_sequence_lock = Lock()


def _new_job_id() -> str:
    with _sequence_lock:
        number = next(_sequence)
    return f"APPROVAL-REVIEW-{datetime.now():%Y%m%d}-{number:04d}"


@router.post(
    "",
    response_model=ApprovalReviewStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_approval_review(
    request: ApprovalReviewRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
) -> ApprovalReviewStartResponse:
    repository = ApprovalReviewRepository(session)
    if repository.get_docs(request.docs_sn) is None:
        raise HTTPException(status_code=404, detail="검토 대상 산출물이 없습니다.")
    if repository.get_docs_detail(
        request.docs_sn, request.approval_request_docs_dtl_sn
    ) is None:
        raise HTTPException(status_code=404, detail="승인 요청 상세 산출물이 없습니다.")

    job_id = _new_job_id()
    repository.create_approval_review_job(
        job_id, request.docs_sn, request.approval_request_docs_dtl_sn
    )
    background_tasks.add_task(
        _run_review,
        job_id,
        request.docs_sn,
        request.approval_request_docs_dtl_sn,
    )
    return ApprovalReviewStartResponse(job_id=job_id, status="processing")


@router.get("/{job_id}", response_model=ApprovalReviewJobResponse)
def get_approval_review(
    job_id: str, session: Session = Depends(get_db_session)
) -> ApprovalReviewJobResponse:
    job = ApprovalReviewRepository(session).get_approval_review_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="검토 작업을 찾을 수 없습니다.")
    return ApprovalReviewJobResponse(
        job_id=job_id,
        status=job["status"],
        result=job["result"],
        error_message=job["error_message"],
    )


def _run_review(job_id: str, docs_sn: int, after_docs_dtl_sn: int) -> None:
    session = SessionLocal()
    repository = ApprovalReviewRepository(session)
    try:
        result = ApprovalReviewAgent(repository).execute(docs_sn, after_docs_dtl_sn)
        repository.update_approval_review_job(job_id, status="done", result=result)
    except Exception as exc:
        logger.exception("Approval artifact review failed job_id=%s", job_id)
        repository.update_approval_review_job(
            job_id, status="failed", error_message=str(exc)
        )
    finally:
        session.close()
