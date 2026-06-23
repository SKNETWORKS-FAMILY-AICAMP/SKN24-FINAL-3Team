from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class GenerationJob(Base):
    """산출물 생성 비동기 작업을 관리하는 ORM 모델입니다."""

    __tablename__ = "tbl_generation_job"
    __table_args__ = (
        UniqueConstraint("job_id", name="uk_generation_job_id"),
        UniqueConstraint("active_key", name="uk_generation_job_active_key"),
    )

    job_sn: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False)

    prj_sn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    docs_cd: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    docs_sn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_docs_dtl_sn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    job_stts_cd: Mapped[str] = mapped_column(
        String(30), nullable=False, default="QUEUED", index=True
    )
    job_step_cd: Mapped[str | None] = mapped_column(String(50), nullable=True)
    progress_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_cn: Mapped[str | None] = mapped_column(String(500), nullable=True)

    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_cd: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    retry_cnt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 현재 export 단계는 완전한 멱등성이 보장되지 않으므로 자동 재시도는 기본 비활성화합니다.
    max_retry_cnt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

    requested_dt: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    started_dt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_dt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_dt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_dt: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    @property
    def project_sn(self) -> int:
        return self.prj_sn
