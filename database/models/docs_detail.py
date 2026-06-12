from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class DocsDetail(Base):
    """tbl_docs_detail ORM placeholder입니다."""

    __tablename__ = "tbl_docs_detail"

    docs_detail_sn: Mapped[int] = mapped_column(Integer, primary_key=True)
