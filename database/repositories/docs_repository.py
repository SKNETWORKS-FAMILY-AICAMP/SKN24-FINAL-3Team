from typing import Any

from sqlalchemy.orm import Session

from schemas.common.common_schema import DocsCode


class DocsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_docs_cd(self, docs_cd: DocsCode) -> Any | None:
        raise NotImplementedError

    def list_all(self) -> list[Any]:
        raise NotImplementedError
