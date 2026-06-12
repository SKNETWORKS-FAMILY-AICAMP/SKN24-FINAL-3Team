from typing import Any

from sqlalchemy.orm import Session

from schemas.common.file_schema import FileSn


class FileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_file_sn(self, file_sn: FileSn) -> Any | None:
        raise NotImplementedError

    def get_by_file_sn_list(self, file_sn_list: list[FileSn]) -> list[Any]:
        raise NotImplementedError

    def create(self, values: dict[str, Any]) -> Any:
        raise NotImplementedError
