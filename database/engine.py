import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다.")


def create_database_engine(database_url: str = DATABASE_URL) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


engine = create_database_engine()
