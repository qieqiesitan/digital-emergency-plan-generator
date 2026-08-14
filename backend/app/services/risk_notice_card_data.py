"""风险告知卡常量：GB 6441-1986 二十类事故 → 安全标志组、应急处置模板。

标志图形完全符合 GB 2894-2025《安全色和安全标志》：
警告=黄底黑边正三角 / 禁止=白底红圈红斜杠 / 指令=蓝底白圆 / 提示=绿底白方。
"""

from app.services.risk_mapping_service import LEVEL_COLORS

# 安全标志排列顺序（GB 2894-2025：警告→禁止→指令→提示）
SIGN_CATEGORY_ORDER = ["warning", "prohibition", "instruction", "notice"]

# 标志名称常量（与 SVG 资产、GB 2894-2025 标准名称一致）
W = lambda name, svg: {"category": "warning", "name": name, "svg_name": svg}
P = lambda name, svg: {"category": "prohibition", "name": name, "svg_name": svg}
I = lambda name, svg: {"category": "instruction", "name": name, "svg_name": svg}
N = lambda name, svg: {"category": "notice", "name": name, "svg_name": svg}

GB6441_ACCIDENT_TYPES = [
    "物体打击", "车辆伤害", "机械伤害", "起重伤害", "触电", "淹溺", "灼烫",
    "火灾", "高处坠落", "坍塌", "冒顶片帮", "透水", "放炮", "火药爆炸",
    "瓦斯爆炸", "锅炉爆炸", "容器爆炸", "其他爆炸", "中毒和窒息", "其他伤害",
]

# 事故类型 → 标志组（每个类别（警告/禁止/指令/提示）最多 2 个，顺序已符合 警告→禁止→指令→提示）
SIGN_GROUPS: dict[str, list[dict]] = {
    "物体打击": [W("当心坠落物", "warning-falling-object"), I("必须戴安全帽", "instruction-helmet")],
    "车辆伤害": [W("当心车辆", "warning-vehicle"), P("禁止通行", "prohibition-pass"), N("紧急出口", "notice-exit")],
    "机械伤害": [W("当心机械伤人", "warning-machinery"), I("必须戴防护手套", "instruction-gloves")],
    "起重伤害": [W("当心起重伤害", "warning-crane"), P("禁止站人", "prohibition-standing"), I("必须戴安全帽", "instruction-helmet")],
    "触电": [W("当心触电", "warning-electric"), P("禁止触摸", "prohibition-touch"),
             I("必须穿绝缘鞋", "instruction-insulating-shoes"), I("必须戴防护手套", "instruction-gloves"), N("紧急出口", "notice-exit")],
    "淹溺": [W("当心落水", "warning-drowning"), I("必须穿救生衣", "instruction-lifejacket")],
    # 洗眼台仅用于化学灼伤/腐蚀品溅眼（如酸/碱作业），热烫伤不适用，故不放通用灼烫组
    "灼烫": [W("当心烫伤", "warning-burn"), I("必须穿防护服", "instruction-protective-suit"),
             I("必须戴防护手套", "instruction-gloves")],
    "火灾": [W("当心火灾", "warning-fire"), P("禁止烟火", "prohibition-smoking"),
             P("禁止动火作业", "prohibition-hot-work"), N("紧急出口", "notice-exit")],
    "高处坠落": [W("当心坠落", "warning-fall"), P("禁止抛物", "prohibition-throwing"), I("必须系安全带", "instruction-seatbelt")],
    "坍塌": [W("当心坍塌", "warning-collapse"), P("禁止通行", "prohibition-pass")],
    "冒顶片帮": [W("当心冒顶", "warning-roof-fall"), I("必须戴安全帽", "instruction-helmet")],
    "透水": [W("当心透水", "warning-water-inrush"), I("必须穿救生衣", "instruction-lifejacket")],
    "放炮": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"), I("必须戴安全帽", "instruction-helmet")],
    "火药爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 P("禁止动火作业", "prohibition-hot-work"), I("必须消除静电", "instruction-eliminate-static")],
    "瓦斯爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 I("必须消除静电", "instruction-eliminate-static"), I("必须穿防静电工作服", "instruction-anti-static-clothes")],
    "锅炉爆炸": [W("当心爆炸", "warning-explosion"), I("必须消除静电", "instruction-eliminate-static")],
    "容器爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 I("必须消除静电", "instruction-eliminate-static")],
    "其他爆炸": [W("当心爆炸", "warning-explosion"), P("禁止烟火", "prohibition-smoking"),
                 I("必须消除静电", "instruction-eliminate-static")],
    "中毒和窒息": [W("当心中毒", "warning-poison"), W("当心窒息", "warning-suffocation"),
                    I("必须戴防毒面具", "instruction-gas-mask"), I("必须通风", "instruction-ventilate")],
    "其他伤害": [W("当心机械伤人", "warning-machinery"), P("禁止烟火", "prohibition-smoking"),
                 I("必须戴安全帽", "instruction-helmet"), N("紧急出口", "notice-exit")],
}

DEFAULT_SIGN_GROUP = list(SIGN_GROUPS["其他伤害"])

# 快照来源常量：AI 优化结果
SOURCE_AI = "ai"

# 应急措施兜底模板：没有任何事故类型模板可用时使用
DEFAULT_EMERGENCY_TEMPLATE = ["立即停止作业，保护现场", "拨打 119/120 报警", "组织人员疏散，报告企业应急管理部门"]

# 应急处置模板（事故类型 → 标准步骤；emergency 措施不足 2 条时兜底）
EMERGENCY_TEMPLATES: dict[str, list[str]] = {
    "物体打击": ["立即停止作业，保护现场", "对伤员止血包扎，尽快送医", "拨打 120 急救电话", "报告企业安全管理部门"],
    "车辆伤害": ["立即制动熄火，设置警戒", "现场急救伤员，拨打 120", "保护现场，配合事故调查"],
    "机械伤害": ["立即停机断电", "对伤员止血包扎固定，拨打 120", "保护现场，禁止移动伤者"],
    "起重伤害": ["立即停止起吊作业", "抢救伤员并拨打 120", "设置警戒区，保护现场"],
    "触电": ["立即切断电源或用绝缘物使伤员脱离电源", "判断意识与呼吸，必要时心肺复苏", "拨打 120，持续施救至医务人员到达"],
    "淹溺": ["立即将溺水者救出水面", "清理口鼻异物，判断呼吸，必要时心肺复苏", "拨打 120，注意保暖"],
    "灼烫": ["立即用大量清水冲洗创面 15 分钟以上", "小心脱除衣物，避免撕扯", "覆盖创面送医，拨打 120"],
    "火灾": ["立即切断气源、电源，停止作业", "拨打 119 报警并报告企业应急指挥部", "组织人员从上风向撤离，清点人数", "使用灭火器材初期扑救，禁止盲目进入"],
    "高处坠落": ["保持伤员静止，勿随意搬动", "固定伤者后平稳搬运", "拨打 120，保护现场"],
    "坍塌": ["立即设置警戒，禁止无关人员进入", "防止二次坍塌，谨慎搜救", "拨打 119/120 请求专业救援"],
    "冒顶片帮": ["立即撤出危险区域，设置警戒", "在确保支护安全前提下搜救", "拨打 120，报告矿方调度"],
    "透水": ["立即沿避灾路线撤离，发出警报", "报告调度，清点人数", "在安全地点等待救援"],
    "放炮": ["立即停止作业，警戒隔离", "确认无二次爆破风险后施救", "拨打 120，保护现场"],
    "火药爆炸": ["立即切断电源与火源，撤离现场", "拨打 119/120 报警", "清点人数，配合专业救援"],
    "瓦斯爆炸": ["立即切断电源，组织撤离", "拨打 119/120 报警", "严禁火源，通风排放，配合救援"],
    "锅炉爆炸": ["立即停炉断电，撤离现场", "拨打 119/120 报警", "清点人数，防止二次爆炸"],
    "容器爆炸": ["立即切断气源电源，撤离", "拨打 119/120 报警", "警戒隔离，配合专业处置"],
    "其他爆炸": ["立即切断电源与火源，撤离", "拨打 119/120 报警", "警戒隔离，配合专业处置"],
    "中毒和窒息": ["佩戴防护用品后进入，禁止盲目施救", "立即通风，将伤员移至新鲜空气处", "拨打 120，必要时心肺复苏", "报警并报告企业应急指挥部"],
    "其他伤害": ["立即停止作业，现场急救", "拨打 120 送医", "报告企业安全管理部门"],
}

# 风险等级排序（大 → 小），用于取最高等级；
# 与 risk_mapping_service.LEVEL_ORDER（等级权重字典）用途不同，勿混用
LEVEL_ORDER = ["重大", "较大", "一般", "低"]
