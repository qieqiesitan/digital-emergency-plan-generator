"""B1 回归测试：危化品 AI 提示词中文不得为 `?` 乱码（见 docs/项目体检报告-2026-09-02.md B1）。

该文件曾发生编码事故，system_prompt / user_prompt / 404 文案整段被替换为
连续的 `?`（发给 LLM 的是问号串）。本测试扫描源码关键 prompt 段：
不得出现连续 `?` 占位，且恢复后的关键中文文案必须存在。
"""

import pathlib


ROUTER_PATH = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "hazardous_chemicals.py"


def _source() -> str:
    assert ROUTER_PATH.exists(), f"源码不存在: {ROUTER_PATH}"
    return ROUTER_PATH.read_text(encoding="utf-8")


def test_no_question_mark_mojibake_in_source():
    """源码关键 prompt 段不得含连续 `?` 占位（历史乱码形态为 `?????`）。"""
    src = _source()
    assert "?????" not in src


def test_404_messages_restored_in_chinese():
    src = _source()
    assert "企业不存在" in src
    assert "危化品不存在" in src


def test_ai_questions_prompt_restored():
    src = _source()
    # AI 提问 system_prompt：危化品辨识专家 + 法规依据
    assert "危险化学品目录（2015版）" in src
    assert "GB 12268-2012" in src
    assert "已录入的危化品不要重复提问" in src
    # 提问 user_prompt：JSON 输出契约（源码为 f-string，花括号成对转义）
    assert '"questions": [{{"id": "q1", "question": "问题文本"}}]' in src
    assert "只输出 JSON" in src


def test_ai_generate_prompt_restored():
    src = _source()
    assert "严禁生成与已录入危化品名称相同或实质重复的危化品" in src
    # 生成 user_prompt：字段契约与 schema 一致
    for field in (
        "name: 危化品名称",
        "cas_no: CAS 编号",
        "un_no: UN 编号",
        "physical_state: 物理状态",
        "flash_point: 闪点",
        "explosion_limit: 爆炸极限",
        "ignition_temp: 引燃温度",
        "density: 密度",
        "boiling_point: 沸点",
        "health_hazard: 健康危害",
        "fire_hazard: 火灾危险性",
        "leak_response: 泄漏应急处理",
        "storage_transport: 储存运输注意事项",
        "first_aid: 急救措施",
        "protective_measures: 防护措施",
        "location: 存放位置",
        "max_storage: 最大储存量",
    ):
        assert field in src, f"缺少生成字段说明: {field}"
    assert '"cas_no": "8006-14-2"' in src


def test_error_and_empty_messages_restored():
    src = _source()
    assert "AI 返回格式异常，无法解析 JSON" in src
    assert "AI 调用失败" in src
    assert "至少需要一个危化品" in src
