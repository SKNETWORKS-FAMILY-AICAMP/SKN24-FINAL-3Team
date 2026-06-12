from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SearchTarget = Literal["RAG", "WEB", "BOTH", "NONE"]
SearchSource = Literal["RAG", "WEB"]


class SearchRequest(BaseModel):
    """Agent가 Search Tool에 전달하는 검색 요청입니다."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    search_targets: SearchTarget = "RAG"
    filters: dict[str, Any] | None = None
    top_k: int = Field(default=5, ge=1, le=100)
    query_vector: list[float] | None = None
    collection: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("query는 비어 있을 수 없습니다.")
        return query


class SearchResult(BaseModel):
    """RAG/Web 검색 결과의 공통 형식입니다."""

    model_config = ConfigDict(extra="forbid")

    source: SearchSource
    id: str | int
    title: str = ""
    content: str = ""
    url: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
