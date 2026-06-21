from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from config.settings import Settings, get_settings


class ApprovalReviewRepository:
    _jobs: dict[str, dict[str, Any]] = {}
    _jobs_lock = Lock()

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def get_docs(self, docs_sn: int) -> dict[str, Any] | None:
        row = self.session.execute(
            text(
                """
                SELECT docs_sn, prj_sn, psn_user_sn, docs_cd, docs_ver,
                       docs_prgrs_stts_cd, mdfcn_cn, crt_dt, creatr_sn,
                       mdfcn_dt, mdfr_sn
                FROM tbl_docs
                WHERE docs_sn = :docs_sn
                """
            ),
            {"docs_sn": docs_sn},
        ).mappings().first()
        return dict(row) if row is not None else None

    def get_first_docs_detail(self, docs_sn: int) -> dict[str, Any] | None:
        row = self.session.execute(
            text(
                """
                SELECT docs_dtl_sn, docs_sn, docs_dtl_cn, docs_path,
                       del_yn, crt_dt, creatr_sn
                FROM tbl_docs_detail
                WHERE docs_sn = :docs_sn
                  AND del_yn = 'N'
                ORDER BY crt_dt ASC, docs_dtl_sn ASC
                LIMIT 1
                """
            ),
            {"docs_sn": docs_sn},
        ).mappings().first()
        return dict(row) if row is not None else None

    def get_docs_detail(
        self, docs_sn: int, docs_dtl_sn: int
    ) -> dict[str, Any] | None:
        row = self.session.execute(
            text(
                """
                SELECT docs_dtl_sn, docs_sn, docs_dtl_cn, docs_path,
                       del_yn, crt_dt, creatr_sn
                FROM tbl_docs_detail
                WHERE docs_sn = :docs_sn
                  AND docs_dtl_sn = :docs_dtl_sn
                  AND del_yn = 'N'
                """
            ),
            {"docs_sn": docs_sn, "docs_dtl_sn": docs_dtl_sn},
        ).mappings().first()
        return dict(row) if row is not None else None

    def get_latest_fixed_requirement_detail(
        self, prj_sn: int
    ) -> dict[str, Any] | None:
        statement = text(
            """
            SELECT d.docs_sn, d.prj_sn, d.docs_cd, d.docs_ver,
                   d.docs_prgrs_stts_cd, dd.docs_dtl_sn, dd.docs_dtl_cn,
                   dd.docs_path, dd.crt_dt
            FROM tbl_docs d
            JOIN tbl_docs_detail dd ON d.docs_sn = dd.docs_sn
            WHERE d.prj_sn = :prj_sn
              AND d.docs_cd IN :requirement_docs_codes
              AND d.docs_prgrs_stts_cd IN :fixed_status_codes
              AND dd.del_yn = 'N'
            ORDER BY d.mdfcn_dt DESC, dd.crt_dt DESC, dd.docs_dtl_sn DESC
            LIMIT 1
            """
        ).bindparams(
            bindparam("requirement_docs_codes", expanding=True),
            bindparam("fixed_status_codes", expanding=True),
        )
        row = self.session.execute(
            statement,
            {
                "prj_sn": prj_sn,
                "requirement_docs_codes": self.settings.requirement_docs_codes,
                "fixed_status_codes": self.settings.fixed_status_codes,
            },
        ).mappings().first()
        return dict(row) if row is not None else None

    def create_approval_review_job(
        self, job_id: str, docs_sn: int, after_docs_dtl_sn: int
    ) -> dict[str, Any]:
        job = {
            "job_id": job_id,
            "docs_sn": docs_sn,
            "after_docs_dtl_sn": after_docs_dtl_sn,
            "status": "processing",
            "result": None,
            "error_message": None,
            "crt_dt": datetime.now(),
            "udt_dt": None,
        }
        with self._jobs_lock:
            self._jobs[job_id] = job
        return dict(job)

    def update_approval_review_job(
        self,
        job_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        with self._jobs_lock:
            if job_id not in self._jobs:
                raise LookupError(f"approval review job not found: {job_id}")
            self._jobs[job_id].update(
                {
                    "status": status,
                    "result": result,
                    "error_message": error_message,
                    "udt_dt": datetime.now(),
                }
            )
            return dict(self._jobs[job_id])

    def get_approval_review_job(self, job_id: str) -> dict[str, Any] | None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            return dict(job) if job is not None else None
