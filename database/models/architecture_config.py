from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class ArchitectureConfig(Base):
    """아키텍처 설정 테이블 ORM placeholder입니다."""

    __tablename__ = "tbl_architecture_config"

    architecture_config_sn: Mapped[int] = mapped_column(Integer, primary_key=True)
