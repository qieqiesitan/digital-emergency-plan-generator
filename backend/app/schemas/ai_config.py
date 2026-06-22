from pydantic import BaseModel

class AIConfigCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    provider: str; api_key: str; model_name: str; base_url: str | None = None
    temperature: float = 0.7; max_tokens: int = 4096; top_p: float = 1.0

class AIConfigUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}
    provider: str | None = None; api_key: str | None = None; model_name: str | None = None
    base_url: str | None = None; temperature: float | None = None
    max_tokens: int | None = None; top_p: float | None = None

class AIConfigResponse(BaseModel):
    model_config = {"protected_namespaces": (), "from_attributes": True}
    id: str; provider: str; model_name: str; base_url: str | None
    temperature: float; max_tokens: int; top_p: float; is_active: bool; last_test_at: str | None

class AITestRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    provider: str; api_key: str; model_name: str; base_url: str | None = None

class AITestResult(BaseModel):
    ok: bool; detail: str
