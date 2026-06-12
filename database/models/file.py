from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class File(Base):
    """tbl_file ORM placeholder입니다."""

    __tablename__ = "tbl_file"

    file_sn: Mapped[int] = mapped_column(Integer, primary_key=True)
