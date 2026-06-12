from typing import Any

from sqlalchemy.orm import Session


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_project_sn(self, project_sn: int) -> Any | None:
        raise NotImplementedError

    def exists(self, project_sn: int) -> bool:
        raise NotImplementedError
