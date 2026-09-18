"""平台级出入参。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CapabilityOut(BaseModel):
    id: str
    code: str
    module: str
    name: str
    description: Optional[str] = None
    prompt_ref: Optional[str] = None
    model_override: Optional[str] = None
    is_enabled: bool
    allow_manual: bool

    # model_override 与 pydantic 的 model_ 保护前缀冲突，按仓库既有约定放开（见 schemas/ai_config.py）
    model_config = {"protected_namespaces": (), "from_attributes": True}


class CapabilityUpdateIn(BaseModel):
    is_enabled: Optional[bool] = None
    allow_manual: Optional[bool] = None
    model_override: Optional[str] = None
    prompt_ref: Optional[str] = None

    model_config = {"protected_namespaces": ()}
