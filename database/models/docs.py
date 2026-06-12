from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Docs(Base):
    """tbl_docs ORM placeholder입니다."""

    __tablename__ = "tbl_docs"

    docs_cd: Mapped[str] = mapped_column(String(20), primary_key=True)
