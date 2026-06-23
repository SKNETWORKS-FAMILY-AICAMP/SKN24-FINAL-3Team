from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.generation_job import GenerationJob


TERMINAL_JOB_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED"}


class GenerationJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        job_id: str,
        project_sn: int,
        docs_cd: str,
        request_json: dict[str, Any],
        request_id: str | None,
        docs_sn: int | None = None,
        request_docs_detail_sn: int | None = None,
        max_retry_count: int = 0,
    ) -> GenerationJob:
        job = GenerationJob(
            job_id=job_id,
            prj_sn=project_sn,
            docs_cd=docs_cd,
            docs_sn=docs_sn,
            request_docs_dtl_sn=request_docs_detail_sn,
            job_stts_cd="QUEUED",
            progress_rate=0,
            message_cn="작업 대기 중입니다.",
            request_json=request_json,
            request_id=request_id,
            retry_cnt=0,
            max_retry_cnt=max_retry_count,
            active_key=f"{project_sn}:{docs_cd}",
        )
        self.session.add(job)
        self.session.flush()
        return job

    def find_by_job_id(self, job_id: str) -> GenerationJob | None:
        return self.session.scalar(
            select(GenerationJob).where(GenerationJob.job_id == job_id)
        )

    def find_active(self, project_sn: int, docs_cd: str) -> GenerationJob | None:
        return self.session.scalar(
            select(GenerationJob)
            .where(
                GenerationJob.prj_sn == project_sn,
                GenerationJob.docs_cd == docs_cd,
                GenerationJob.job_stts_cd.in_(("QUEUED", "RUNNING", "CANCEL_REQUESTED")),
            )
            .order_by(GenerationJob.job_sn.desc())
            .limit(1)
        )

    def claim_next(self, worker_id: str) -> GenerationJob | None:
        statement = (
            select(GenerationJob)
            .where(GenerationJob.job_stts_cd == "QUEUED")
            .order_by(GenerationJob.requested_dt, GenerationJob.job_sn)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = self.session.scalar(statement)
        if job is None:
            return None

        now = datetime.now()
        job.job_stts_cd = "RUNNING"
        job.job_step_cd = "PREPROCESSING"
        job.progress_rate = 5
        job.message_cn = "산출물 생성 작업을 시작합니다."
        job.worker_id = worker_id
        job.started_dt = job.started_dt or now
        job.heartbeat_dt = now
        self.session.flush()
        return job

    def recover_stale_jobs(self, stale_before: datetime) -> tuple[int, int]:
        jobs = self.session.scalars(
            select(GenerationJob)
            .where(
                GenerationJob.job_stts_cd == "RUNNING",
                GenerationJob.heartbeat_dt < stale_before,
            )
            .with_for_update(skip_locked=True)
        ).all()
        requeued = 0
        failed = 0
        for job in jobs:
            if job.retry_cnt < job.max_retry_cnt:
                job.retry_cnt += 1
                job.job_stts_cd = "QUEUED"
                job.job_step_cd = None
                job.progress_rate = 0
                job.message_cn = "중단된 작업을 다시 대기열에 등록했습니다."
                job.worker_id = None
                job.heartbeat_dt = None
                requeued += 1
                continue

            now = datetime.now()
            job.job_stts_cd = "FAILED"
            job.message_cn = "Worker 응답이 없어 작업이 실패 처리되었습니다."
            job.error_cd = "GENERATION_WORKER_STALE"
            job.error_msg = "작업 Worker의 heartbeat가 제한 시간 동안 갱신되지 않았습니다."
            job.completed_dt = now
            job.active_key = None
            failed += 1
        self.session.flush()
        return requeued, failed

    def update_progress(
        self,
        job_id: str,
        *,
        step: str,
        progress: int,
        message: str,
    ) -> GenerationJob | None:
        job = self.find_by_job_id(job_id)
        if job is None or job.job_stts_cd in TERMINAL_JOB_STATUSES:
            return job
        job.job_step_cd = step
        job.progress_rate = max(job.progress_rate, min(max(progress, 0), 99))
        job.message_cn = message
        job.heartbeat_dt = datetime.now()
        self.session.flush()
        return job

    def touch_heartbeat(self, job_id: str) -> None:
        job = self.find_by_job_id(job_id)
        if job is not None and job.job_stts_cd == "RUNNING":
            job.heartbeat_dt = datetime.now()
            self.session.flush()

    def mark_succeeded(
        self,
        job_id: str,
        result: dict[str, Any],
    ) -> GenerationJob | None:
        job = self.find_by_job_id(job_id)
        if job is None:
            return None
        now = datetime.now()
        job.job_stts_cd = "SUCCEEDED"
        job.job_step_cd = "COMPLETED"
        job.progress_rate = 100
        job.message_cn = "산출물 생성이 완료되었습니다."
        job.result_json = result
        job.error_cd = None
        job.error_msg = None
        job.completed_dt = now
        job.heartbeat_dt = now
        job.active_key = None
        self.session.flush()
        return job

    def mark_failed(
        self,
        job_id: str,
        *,
        error_code: str,
        error_message: str,
        result: dict[str, Any] | None = None,
    ) -> GenerationJob | None:
        job = self.find_by_job_id(job_id)
        if job is None:
            return None
        now = datetime.now()
        job.job_stts_cd = "FAILED"
        job.message_cn = "산출물 생성에 실패했습니다."
        job.result_json = result
        job.error_cd = error_code
        job.error_msg = error_message
        job.completed_dt = now
        job.heartbeat_dt = now
        job.active_key = None
        self.session.flush()
        return job
