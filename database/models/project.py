from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Project(Base):
    """tbl_project ORM placeholder입니다."""

    __tablename__ = "tbl_project"

    project_sn: Mapped[int] = mapped_column(Integer, primary_key=True)
