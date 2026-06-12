from typing import Any

from sqlalchemy.orm import Session

from schemas.common.common_schema import DocsCode


class DocsDetailRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active(self, project_sn: int, docs_cd: DocsCode) -> Any | None:
        raise NotImplementedError

    def update_progress_status(
        self,
        project_sn: int,
        docs_cd: DocsCode,
        status: str,
        fail_reason: str | None = None,
    ) -> None:
        raise NotImplementedError

    def deactivate_active(self, project_sn: int, docs_cd: DocsCode) -> None:
        raise NotImplementedError

    def create(self, values: dict[str, Any]) -> Any:
        raise NotImplementedError
