"""公开只读风险告知卡（任务 9 填充完整实现）。"""
from fastapi import APIRouter

router = APIRouter(prefix="/public/risk-notice-cards", tags=["Public Risk Notice Card"])
