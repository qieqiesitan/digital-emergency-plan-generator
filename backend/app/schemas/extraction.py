"""抽取相关出入参。"""

from typing import Optional

from pydantic import BaseModel, Field


class SuggestMappingIn(BaseModel):
    headers: list[str] = Field(min_length=1)
    target_entity: str = Field(min_length=1, max_length=60)


class RunExtractionIn(BaseModel):
    job_id: str
    source_id: str
    target_entity: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=1)
    filename: str = Field(min_length=1, max_length=300)
