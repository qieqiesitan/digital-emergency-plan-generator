from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
import json
from pydantic import BaseModel
from app.services.llm_client import llm_text_completion
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.hazardous_chemicals import HazardousChemical
from app.schemas.hazardous_chemicals import (
    HazardousChemicalCreate,
    HazardousChemicalUpdate,
    HazardousChemicalResponse,
)
from app.schemas.common import ApiResponse, PaginatedResponse, PaginatedData

router = APIRouter(prefix="/enterprises", tags=["Hazardous Chemicals"])

# --- AI helpers ---
async def _get_enterprise(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    result = await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id,
            Enterprise.user_id == user_id,
        )
    )
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent


# --- List ---
@router.get("/{enterprise_id}/chemicals", response_model=PaginatedResponse[HazardousChemicalResponse])
async def list_chemicals(
    enterprise_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_enterprise(enterprise_id, current_user.id, db)

    count_q = select(HazardousChemical).where(
        HazardousChemical.enterprise_id == enterprise_id
    )
    total_result = await db.execute(count_q)
    total = len(total_result.scalars().all())

    q = (
        select(HazardousChemical)
        .where(HazardousChemical.enterprise_id == enterprise_id)
        .order_by(HazardousChemical.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    items = result.scalars().all()

    return PaginatedResponse(
        data=PaginatedData(
            items=[HazardousChemicalResponse.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


# --- Get one ---
@router.get("/{enterprise_id}/chemicals/{chemical_id}", response_model=ApiResponse[HazardousChemicalResponse])
async def get_chemical(
    enterprise_id: str,
    chemical_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_enterprise(enterprise_id, current_user.id, db)

    result = await db.execute(
        select(HazardousChemical).where(
            HazardousChemical.id == chemical_id,
            HazardousChemical.enterprise_id == enterprise_id,
        )
    )
    chemical = result.scalar_one_or_none()
    if not chemical:
        raise HTTPException(404, "危化品不存在")

    return ApiResponse(data=HazardousChemicalResponse.model_validate(chemical))


# --- Create ---
@router.post("/{enterprise_id}/chemicals", response_model=ApiResponse[HazardousChemicalResponse], status_code=201)
async def create_chemical(
    enterprise_id: str,
    body: HazardousChemicalCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_enterprise(enterprise_id, current_user.id, db)

    chemical = HazardousChemical(
        enterprise_id=enterprise_id,
        **body.model_dump(exclude_none=True),
    )
    db.add(chemical)
    await db.commit()
    await db.refresh(chemical)

    return ApiResponse(data=HazardousChemicalResponse.model_validate(chemical))


# --- Update ---
@router.put("/{enterprise_id}/chemicals/{chemical_id}", response_model=ApiResponse[HazardousChemicalResponse])
async def update_chemical(
    enterprise_id: str,
    chemical_id: str,
    body: HazardousChemicalUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_enterprise(enterprise_id, current_user.id, db)

    result = await db.execute(
        select(HazardousChemical).where(
            HazardousChemical.id == chemical_id,
            HazardousChemical.enterprise_id == enterprise_id,
        )
    )
    chemical = result.scalar_one_or_none()
    if not chemical:
        raise HTTPException(404, "危化品不存在")

    update_data = body.model_dump(exclude_unset=True, exclude_none=False)
    for key, value in update_data.items():
        setattr(chemical, key, value)

    await db.commit()
    await db.refresh(chemical)

    return ApiResponse(data=HazardousChemicalResponse.model_validate(chemical))


# --- Delete ---
@router.delete("/{enterprise_id}/chemicals/{chemical_id}", response_model=ApiResponse[None])
async def delete_chemical(
    enterprise_id: str,
    chemical_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_enterprise(enterprise_id, current_user.id, db)

    result = await db.execute(
        select(HazardousChemical).where(
            HazardousChemical.id == chemical_id,
            HazardousChemical.enterprise_id == enterprise_id,
        )
    )
    chemical = result.scalar_one_or_none()
    if not chemical:
        raise HTTPException(404, "危化品不存在")

    await db.delete(chemical)
    await db.commit()

    return ApiResponse(data=None)


# --- AI question generation ---
class AIQuestionItem(BaseModel):
    id: str
    question: str


class AIQuestionsResponse(BaseModel):
    questions: list[AIQuestionItem]


@router.post("/{enterprise_id}/chemicals/ai/questions", response_model=ApiResponse[AIQuestionsResponse])
async def get_chemical_ai_questions(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = await _get_enterprise(enterprise_id, current_user.id, db)
    from app.services.ai_config_service import get_system_ai_config
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    # 查询该企业已有的危化品，用于去重
    existing = (await db.execute(
        select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id)
    )).scalars().all()
    existing_names = [c.name for c in existing]
    existing_summary = ""
    if existing_names:
        existing_summary = "\n该企业已录入的危化品（请避免重复提问）：\n"
        for c in existing:
            existing_summary += f"- {c.name}（CAS：{c.cas_no or '未知'}，位置：{c.location or '未指定'}）\n"

    system_prompt = (
        "你是一位持有国家注册安全工程师资格的专业应急预案专家，熟悉《危险化学品目录（2015版）》和危险货物分类标准（GB 12268-2012）。"
        "你的任务是提出针对性问题以帮助识别企业尚未录入的危化品，"
        "必须严格避免对已录入危化品重复提问。"
    )
    user_prompt = f"""请根据以下企业信息，提出 3~5 个针对性问题以辅助识别该企业可能使用、储存的危化品。

问题应结合该企业的行业特点、生产工艺和建筑概况，使用简体中文。

**重要：已录入的危化品不要重复提问，问题应聚焦于尚未覆盖的危化品领域。**

企业信息：
- 名称：{ent.name}
- 行业：{ent.industry or "未知"}
- 经营范围：{ent.business_scope or "未知"}
- 建筑/厂区概况：{ent.building_overview or "未知"}
- 员工人数：{ent.employee_count or "未知"}
{existing_summary}

请以 JSON 格式输出，格式严格为：{{"questions": [{{"id": "q1", "question": "问题文本"}}]}}
只输出 JSON，不要任何解释或额外文本。"""

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


# --- AI generate chemicals ---
class AIAnswerInput(BaseModel):
    question_id: str
    question: str
    answer: str


class AIGenerateRequest(BaseModel):
    answers: list[AIAnswerInput]


class AIGenerateResponse(BaseModel):
    items: list[HazardousChemicalCreate]


@router.post("/{enterprise_id}/chemicals/ai/generate", response_model=ApiResponse[AIGenerateResponse])
async def generate_chemicals_ai(
    enterprise_id: str,
    body: AIGenerateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ent = await _get_enterprise(enterprise_id, current_user.id, db)
    from app.services.ai_config_service import get_system_ai_config
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise HTTPException(400, "系统未配置 AI 模型，请联系管理员")

    # 查询已有危化品，在生成时也做去重参考
    existing = (await db.execute(
        select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id)
    )).scalars().all()
    existing_names = [c.name for c in existing]
    existing_summary = ""
    if existing_names:
        existing_summary = "\n该企业已录入的危化品（严禁重复生成）：\n" + "\n".join(f"- {n}" for n in existing_names)

    qa_text = "\n".join(f"Q: {a.question}\nA: {a.answer}" for a in body.answers)

    system_prompt = (
        "你是一位持有国家注册安全工程师资格的专业应急预案专家，熟悉《危险化学品目录（2015版）》和危险货物分类标准（GB 12268-2012）。"
        "严禁生成与已录入危化品名称相同或实质重复的危化品。"
    )
    user_prompt = f"""请根据以下企业信息和用户回答，识别并列出该企业可能使用、储存的危化品。

企业信息：
- 名称：{ent.name}
- 行业：{ent.industry or "未知"}
- 经营范围：{ent.business_scope or "未知"}
- 建筑/厂区概况：{ent.building_overview or "未知"}
- 员工人数：{ent.employee_count or "未知"}
{existing_summary}

用户回答：
{qa_text}

请列出该企业可能使用、储存的危化品，无法确定的字段填 null：
- name: 危化品名称（简明扼要，必须与已录入危化品名称不重复）
- cas_no: CAS 编号（如已知）
- un_no: UN 编号（如已知）
- physical_state: 物理状态（气态/液态/固态）
- flash_point: 闪点（如适用）
- explosion_limit: 爆炸极限（如适用）
- ignition_temp: 引燃温度（如适用）
- density: 密度（如适用）
- boiling_point: 沸点（如适用）
- health_hazard: 健康危害
- fire_hazard: 火灾危险性
- leak_response: 泄漏应急处理
- storage_transport: 储存运输注意事项
- first_aid: 急救措施
- protective_measures: 防护措施
- location: 存放位置（根据企业信息推测）
- max_storage: 最大储存量（如已知）

请以 JSON 格式输出：{{"items": [{{"name": "危化品名称", "cas_no": "8006-14-2", ...}}]}}
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
        items = [HazardousChemicalCreate(**item) for item in data.get("items", [])]
        return ApiResponse(data=AIGenerateResponse(items=items))
    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(500, f"AI 返回格式异常，无法解析 JSON: {raw[:200]}")
    except Exception as e:
        raise HTTPException(500, f"AI 调用失败: {str(e)}")


# --- Batch create ---
class BatchCreateRequest(BaseModel):
    items: list[HazardousChemicalCreate]


@router.post("/{enterprise_id}/chemicals/batch", response_model=ApiResponse[list[HazardousChemicalResponse]], status_code=201)
async def batch_create_chemicals(
    enterprise_id: str,
    body: BatchCreateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_enterprise(enterprise_id, current_user.id, db)

    if not body.items:
        raise HTTPException(400, "至少需要一个危化品")

    created: list[HazardousChemical] = []
    for item in body.items:
        c = HazardousChemical(
            enterprise_id=enterprise_id,
            **item.model_dump(exclude_none=True),
        )
        db.add(c)
        created.append(c)

    await db.commit()
    for c in created:
        await db.refresh(c)

    return ApiResponse(data=[HazardousChemicalResponse.model_validate(c) for c in created])
