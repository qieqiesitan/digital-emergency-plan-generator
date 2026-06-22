from datetime import datetime as _datetime
from typing import Annotated, Generic, TypeVar, Optional
from pydantic import BaseModel, BeforeValidator

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T

class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

class PaginatedResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: PaginatedData[T]

class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

def _dt2str(v):
    if isinstance(v, _datetime):
        return v.isoformat()
    return v

DatetimeStr = Annotated[str, BeforeValidator(_dt2str)]
