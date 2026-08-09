import json
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import httpx

from app.database import get_db
from app.models.enterprise import Enterprise
from app.schemas.enterprise import SurroundingInfo, NearbyUnit, SensitiveTarget
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user
from app.services.llm_client import llm_text_completion
from app.services.prompt_cache import ensure_loaded

router = APIRouter(prefix="/enterprises", tags=["Surrounding AI"])

# TODO: 方向列表可从 sys_config 加载，当前保持硬编码作为 fallback
DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

# ── Amap POI search ──

AMAP_KEY = "78556e6e7d683bbda1b7d25e24cb412a"

# ponytail: using keywords (text search) instead of type codes for broader coverage
AMAP_POI_KEYWORDS = [
    ("消防站", "消防站", "nearby"),
    ("派出所", "派出所", "nearby"),
    ("综合医院", "综合医院", "nearby"),
    ("加油站", "加油站/加气站", "nearby"),
    ("化工厂", "化工厂", "nearby"),
    ("学校", "学校", "sensitive"),
    ("商场|超市", "商场/超市", "sensitive"),
    ("住宅区|小区", "住宅区", "sensitive"),
    ("公园|广场", "公园/广场", "sensitive"),
]


def _bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> str:
    d_lng = math.radians(lng2 - lng1)
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    x = math.sin(d_lng) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lng)
    bearing_deg = (math.degrees(math.atan2(x, y)) + 360) % 360
    idx = round(bearing_deg / 45) % 8
    return DIRECTIONS[idx]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    R = 6371000
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


async def _geocode_amap(address: str) -> tuple[float, float] | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://restapi.amap.com/v3/geocode/geo", params={
                "key": AMAP_KEY, "address": address, "output": "JSON",
            })
            data = resp.json()
            if data.get("status") == "1" and data.get("geocodes"):
                loc = data["geocodes"][0]["location"]
                lng_str, lat_str = loc.split(",")
                return float(lng_str), float(lat_str)
    except Exception:
        pass
    return None


async def _regeocode_amap(lng: float, lat: float) -> str:
    """Reverse geocode via Amap, returns traffic summary."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://restapi.amap.com/v3/geocode/regeo", params={
                "key": AMAP_KEY, "location": f"{lng},{lat}",
                "radius": 1000, "extensions": "base", "output": "JSON",
            })
            data = resp.json()
            if data.get("status") != "1":
                return ""
            regeo = data.get("regeocode", {})
            addr = regeo.get("addressComponent", {})
            roads_info = regeo.get("roads", [])
            parts = []
            if roads_info:
                road_names = [r.get("name", "") for r in roads_info[:5] if r.get("name")]
                if road_names:
                    parts.append("周边主要道路：" + "、".join(road_names))
            district = addr.get("district", "")
            township = addr.get("township", "")
            if district or township:
                parts.append("位于" + district + township)
            street = addr.get("streetNumber", {}).get("street", "")
            if street:
                parts.append("临近" + street)
            if not parts:
                return regeo.get("formatted_address", "")
            return "。".join(parts) + "。消防车可通行。"
    except Exception:
        return ""


async def _amap_poi_search(lng: float, lat: float, keywords: str, radius: int = 5000) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://restapi.amap.com/v3/place/around", params={
            "key": AMAP_KEY, "location": f"{lng},{lat}", "radius": radius,
            "keywords": keywords, "offset": 10, "output": "JSON",
        })
        return resp.json()


def _risk_for_category(category: str) -> str:
    return {
        "消防站": "火灾", "派出所": "治安事件", "综合医院": "医疗救援",
        "加油站/加气站": "火灾爆炸", "化工厂": "化学泄漏",
    }.get(category, "其他")




async def _get_enterprise_data(enterprise_id: str, user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == user_id)
    )
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return {
        "name": ent.name,
        "industry": ent.industry or "",
        "business_scope": ent.business_scope or "",
        "building_overview": ent.building_overview or "",
        "employee_count": ent.employee_count,
        "address": ent.address or "",
        "hazardous_chemicals": ent.hazardous_chemicals or "",
        "main_products": ent.main_products or "",
        "surrounding_info": ent.surrounding_info or {},
    }


def _build_existing_summary(surrounding: dict) -> str:
    parts = []

    nearby = surrounding.get("nearby_units", [])
    if nearby:
        parts.append("已录入的周边单位：")
        for u in nearby:
            parts.append(f"- {u.get('name','')}（方位：{u.get('direction','')}，距离：{u.get('distance_m','')}m，风险：{u.get('main_risk','')}）")

    targets = surrounding.get("sensitive_targets", [])
    if targets:
        parts.append("已录入的敏感目标：")
        for t in targets:
            parts.append(f"- {t.get('name','')}（方位：{t.get('direction','')}，距离：{t.get('distance_m','')}m，类型：{t.get('type','')}）")

    traffic = surrounding.get("traffic_info", "")
    if traffic:
        parts.append(f"已录入的交通状况：{traffic}")

    return "\n".join(parts) if parts else "当前无周边环境数据"


# ---------- AI question generation ----------

class AIQuestionItem(BaseModel):
    id: str
    question: str


class AIQuestionsResponse(BaseModel):
    questions: list[AIQuestionItem]


@router.post("/{enterprise_id}/surrounding/ai/questions", response_model=ApiResponse[AIQuestionsResponse])
async def get_surrounding_ai_questions(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await ensure_loaded()
    await ensure_loaded()
    ent_data = await _get_enterprise_data(enterprise_id, current_user.id, db)
    from app.services.ai_config_service import get_system_ai_config

    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    existing_summary = _build_existing_summary(ent_data["surrounding_info"])

    system_prompt = (
        "你是一位持有国家注册安全工程师资格的专业应急预案编制专家，熟悉 GB/T 29639-2020 标准。"
        "你的任务是一次性提出全面覆盖周边环境三大板块的调查问题，"
        "严格避免对已录入的周边单位和敏感目标重复提问。"
    )

    user_prompt = f"""请根据以下企业信息，一次性提出 6~10 个全面调查问题，覆盖该企业周边环境的三大板块：
1. 周边单位（相邻工厂、企业、设施的名称、方位、距离、主要风险）
2. 敏感目标（学校、医院、住宅区、水源地、文保单位等的名称、方位、距离、类型）
3. 交通状况（主要进出道路、消防车通行条件、最近高速/国道入口等）

企业信息：
- 名称：{ent_data["name"]}
- 行业：{ent_data["industry"]}
- 经营范围：{ent_data["business_scope"]}
- 地址：{ent_data["address"]}
- 建筑/厂区概况：{ent_data["building_overview"]}
- 员工人数：{ent_data["employee_count"] or "未知"}
- 危险化学品：{ent_data["hazardous_chemicals"]}
- 主要产品：{ent_data["main_products"]}

{existing_summary}

方位参考：{"、".join(DIRECTIONS)}

请以 JSON 格式输出，格式严格为：
{{"questions": [{{"id": "q1", "question": "问题文本"}}]}}
每个板块至少 2 个问题。只输出 JSON，不要任何解释。"""

    try:
        raw = await llm_text_completion(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            ai_config,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if lines[0].startswith("```") else raw
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        data = json.loads(raw)
        questions = [AIQuestionItem(**q) for q in data.get("questions", [])]
        return ApiResponse(data=AIQuestionsResponse(questions=questions))
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(500, f"AI 返回格式异常，无法解析 JSON: {raw[:200]}")
    except Exception as e:
        raise HTTPException(500, f"AI 调用失败: {str(e)}")


# ---------- AI generate surrounding info ----------

class AIAnswerInput(BaseModel):
    question_id: str
    question: str
    answer: str


class AIGenerateRequest(BaseModel):
    answers: list[AIAnswerInput]


class AIGenerateSurroundingResponse(BaseModel):
    surrounding: SurroundingInfo


@router.post("/{enterprise_id}/surrounding/ai/generate", response_model=ApiResponse[AIGenerateSurroundingResponse])
async def generate_surrounding_ai(
    enterprise_id: str,
    body: AIGenerateRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await ensure_loaded()
    ent_data = await _get_enterprise_data(enterprise_id, current_user.id, db)
    from app.services.ai_config_service import get_system_ai_config

    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    existing_summary = _build_existing_summary(ent_data["surrounding_info"])

    qa_text = "\n".join(f"Q: {a.question}\nA: {a.answer}" for a in body.answers)

    system_prompt = (
        "你是一位持有国家注册安全工程师资格的专业应急预案编制专家，熟悉 GB/T 29639-2020 标准。"
        "严禁生成与已录入周边单位/敏感目标名称重复的数据。"
    )

    user_prompt = f"""请根据以下企业信息和用户回答，生成该企业周边环境信息。

企业信息：
- 名称：{ent_data["name"]}
- 行业：{ent_data["industry"]}
- 经营范围：{ent_data["business_scope"]}
- 地址：{ent_data["address"]}
- 建筑/厂区概况：{ent_data["building_overview"]}
- 员工人数：{ent_data["employee_count"] or "未知"}
- 危险化学品：{ent_data["hazardous_chemicals"]}
- 主要产品：{ent_data["main_products"]}

{existing_summary}

用户对周边环境调查的回答：
{qa_text}

请以 JSON 输出，格式严格为：
{{
  "nearby_units": [
    {{"name": "工厂名", "direction": "N", "distance_m": 500, "main_risk": "火灾爆炸"}}
  ],
  "sensitive_targets": [
    {{"name": "XX小学", "direction": "SE", "distance_m": 300, "type": "学校"}}
  ],
  "traffic_info": "主要进出道路为XX路，双向四车道，消防车可通行。距XX高速入口约3公里。"
}}

字段说明：
- direction: 必须从 {DIRECTIONS} 中选择
- distance_m: 整数，单位米
- main_risk: 该单位的主要危险性（火灾/爆炸/中毒/化学泄漏等）
- type: 敏感目标类型（学校/医院/住宅区/水源地/文保单位/商业区等）
- traffic_info: 交通状况的完整文字描述

只输出 JSON，不要任何解释。"""

    try:
        raw = await llm_text_completion(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            ai_config,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if lines[0].startswith("```") else raw
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        data = json.loads(raw)

        nearby_units = [NearbyUnit(**u) for u in data.get("nearby_units", [])]
        sensitive_targets = [SensitiveTarget(**t) for t in data.get("sensitive_targets", [])]
        traffic_info = data.get("traffic_info", "")

        surrounding = SurroundingInfo(
            nearby_units=nearby_units,
            sensitive_targets=sensitive_targets,
            traffic_info=traffic_info,
        )
        return ApiResponse(data=AIGenerateSurroundingResponse(surrounding=surrounding))
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(500, f"AI 返回格式异常，无法解析 JSON: {raw[:200]}")
    except Exception as e:
        raise HTTPException(500, f"AI 调用失败: {str(e)}")
class AmapSearchRequest(BaseModel):
    radius: int = 5000
    types: str | None = None  # comma-separated poi type codes, None = all


class AmapSearchResponse(BaseModel):
    surrounding: SurroundingInfo
    searched_address: str
    has_gis: bool
    available_types: list[dict]  # return available poi types for UI


# ponytail: expose POI type list as endpoint metadata
def _get_available_types() -> list[dict]:
    return [
        {"code": keyword, "label": label, "target_type": target}
        for keyword, label, target in AMAP_POI_KEYWORDS
    ]


@router.post("/{enterprise_id}/surrounding/amap-search", response_model=ApiResponse[AmapSearchResponse])
async def amap_search_surrounding(
    enterprise_id: str,
    body: AmapSearchRequest = AmapSearchRequest(),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id)
    )
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")

    has_gis = ent.gis_lat is not None and ent.gis_lng is not None
    lng, lat = None, None
    searched_address = ent.address or ent.name or ""

    if has_gis:
        lng, lat = ent.gis_lng, ent.gis_lat
    elif ent.address:
        geo = await _geocode_amap(ent.address)
        if geo:
            lng, lat = geo

    if lng is None or lat is None:
        raise HTTPException(400, "企业缺少坐标信息。请在地图上标注厂区位置，或填写完整地址后再试。")

    # Filter POI keywords if specified
    requested_types = None
    if body.types:
        requested_types = set(t.strip() for t in body.types.split(",") if t.strip())
    keywords_to_search = [
        (kw, label, target) for kw, label, target in AMAP_POI_KEYWORDS
        if requested_types is None or kw in requested_types
    ]

    nearby_units: list[dict] = []
    sensitive_targets: list[dict] = []

    for keywords, category, target_type in keywords_to_search:
        try:
            data = await _amap_poi_search(lng, lat, keywords, body.radius)
            if data.get("status") != "1":
                continue
            pois = data.get("pois", [])
            for poi in pois:
                loc = poi.get("location", "")
                if not loc:
                    continue
                try:
                    p_lng_str, p_lat_str = loc.split(",")
                    p_lng, p_lat = float(p_lng_str), float(p_lat_str)
                except ValueError:
                    continue

                dist = _haversine(lat, lng, p_lat, p_lng)
                direction = _bearing(lat, lng, p_lat, p_lng)

                entry = {
                    "name": poi.get("name", ""),
                    "direction": direction,
                    "distance_m": dist,
                }

                if target_type == "nearby":
                    entry["main_risk"] = _risk_for_category(category)
                    nearby_units.append(entry)
                else:
                    entry["type"] = category
                    sensitive_targets.append(entry)
        except Exception:
            continue

    seen = set()
    nearby_units = [u for u in nearby_units if not (u["name"] in seen or seen.add(u["name"]))]
    seen.clear()
    sensitive_targets = [t for t in sensitive_targets if not (t["name"] in seen or seen.add(t["name"]))]

    # Generate traffic info from reverse geocode
    traffic_info = await _regeocode_amap(lng, lat)

    surrounding = SurroundingInfo(
        nearby_units=[NearbyUnit(**u) for u in nearby_units],
        sensitive_targets=[SensitiveTarget(**t) for t in sensitive_targets],
        traffic_info=traffic_info,
    )

    return ApiResponse(data=AmapSearchResponse(
        surrounding=surrounding,
        searched_address=searched_address,
        has_gis=has_gis,
        available_types=_get_available_types(),
    ))
