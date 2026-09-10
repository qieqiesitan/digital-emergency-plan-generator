"""报告 GET 响应必须原样透传 JSONB summary（含 chapters/images），
否则前端工作台重挂载后拿不到草稿章节，表现为“生成后不合并返回再进入需重新生成”。"""

from datetime import datetime
from types import SimpleNamespace

from app.schemas.resource_investigation import ResourceInvestigationReportResponse
from app.schemas.risk_assessment import RiskAssessmentReportResponse


def _report_with_summary(summary: dict):
    now = datetime(2026, 9, 3, 6, 58, 19)
    return SimpleNamespace(
        id="r1",
        enterprise_id="e1",
        title="风险评估报告",
        content="# 正文",
        summary=summary,
        status="draft",
        generated_by="ai",
        generated_at=now,
        created_at=now,
        updated_at=now,
    )


def test_risk_response_keeps_summary_chapters_and_images():
    """草稿 summary 中的 chapters/images 不能被响应 schema 过滤掉。"""
    summary = {
        "chapters": [
            {"key": "ch1_hazard_id", "title": "一、危险有害因素辨识分析", "content": "辨识内容"},
            {"key": "ch3_risk_eval", "title": "三、风险等级评估", "content": "评估内容"},
        ],
        "images": [{"floor_id": "f1", "floor_name": "一层", "url": "/uploads/enterprises/e1/f1.png"}],
        "overall_assessment": "总体风险可控",
    }
    payload = RiskAssessmentReportResponse.model_validate(_report_with_summary(summary)).model_dump()
    assert payload["summary"]["chapters"] == summary["chapters"]
    assert payload["summary"]["images"] == summary["images"]
    assert payload["summary"]["overall_assessment"] == "总体风险可控"


def test_resource_response_keeps_summary_chapters():
    summary = {
        "chapters": [{"key": "ch1_purpose", "title": "一、调查目的与依据", "content": "调查内容"}],
        "overall_assessment": "资源基本满足",
    }
    payload = ResourceInvestigationReportResponse.model_validate(
        _report_with_summary(summary)
    ).model_dump()
    assert payload["summary"]["chapters"] == summary["chapters"]
    assert payload["summary"]["overall_assessment"] == "资源基本满足"
