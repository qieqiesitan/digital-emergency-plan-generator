from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
import json
from pydantic import BaseModel
from app.models.enterprise import AIConfig
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

# ?? AI helpers ??
async def _get_enterprise(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    result = await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id,
            Enterprise.user_id == user_id,
        )
    )
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "?????")
    return ent


# ?? List ??
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


# ?? Get one ??
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
        raise HTTPException(404, "??????????")

    return ApiResponse(data=HazardousChemicalResponse.model_validate(chemical))


# ?? Create ??
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


# ?? Update ??
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
        raise HTTPException(404, "??????????")

    update_data = body.model_dump(exclude_unset=True, exclude_none=False)
    for key, value in update_data.items():
        setattr(chemical, key, value)

    await db.commit()
    await db.refresh(chemical)

    return ApiResponse(data=HazardousChemicalResponse.model_validate(chemical))


# ?? Delete ??
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
        raise HTTPException(404, "??????????")

    await db.delete(chemical)
    await db.commit()

    return ApiResponse(data=None)


# ?? AI question generation ??
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
    ai_config = (await db.execute(
        select(AIConfig).where(AIConfig.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ai_config:
        raise HTTPException(400, "?????????? AI ??")

    # ???????
    existing = (await db.execute(
        select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id)
    )).scalars().all()
    existing_names = [c.name for c in existing]
    existing_summary = ""
    if existing_names:
        existing_summary = "\n??????????????????????\n"
        for c in existing:
            existing_summary += f"- {c.name}?CAS: {c.cas_no or '?'}?????: {c.location or '???'}?\n"

    system_prompt = (
        "?????????????????????????????"
        "???????????2015?????????????(GB 12268-2012)?"
        "????????????????????????????"
        "???????????????????"
    )
    user_prompt = f"""???????????? 3~5 ?????????????????????????

????????????????????????????????????????????????????

**?????????????????**

?????
- ???{ent.name}
- ???{ent.industry or "??"}
- ?????{ent.business_scope or "??"}
- ??/?????{ent.building_overview or "??"}
- ?????{ent.employee_count or "??"}
{existing_summary}

?? JSON ?????{{"questions": [{{"id": "q1", "question": "????"}}]}}
??? JSON????????"""

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
        raise HTTPException(500, f"AI ??????: {raw[:200]}")
    except Exception as e:
        raise HTTPException(500, f"AI ????: {str(e)}")


# ?? AI generate chemicals ??
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
    ai_config = (await db.execute(
        select(AIConfig).where(AIConfig.user_id == current_user.id)
    )).scalar_one_or_none()
    if not ai_config:
        raise HTTPException(400, "?????????? AI ??")

    # ?????????????
    existing = (await db.execute(
        select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id)
    )).scalars().all()
    existing_names = [c.name for c in existing]
    existing_summary = ""
    if existing_names:
        existing_summary = "\n?????????????????????\n" + "\n".join(f"- {n}" for n in existing_names)

    qa_text = "\n".join(f"Q: {a.question}\nA: {a.answer}" for a in body.answers)

    system_prompt = (
        "?????????????????????????????"
        "???????????2015?????????????(GB 12268-2012)?"
        "????????????????????????"
        "?????????????????????????????????"
    )
    user_prompt = f"""???????????????????????????????

?????
- ???{ent.name}
- ???{ent.industry or "??"}
- ?????{ent.business_scope or "??"}
- ??/?????{ent.building_overview or "??"}
- ?????{ent.employee_count or "??"}
{existing_summary}

?????
{qa_text}

????????????????????????? null??
- name: ??????????????????
- cas_no: CAS??????
- un_no: UN??????
- physical_state: ???????/??/???
- flash_point: ???????????
- explosion_limit: ?????????????
- ignition_temp: ?????????
- density: ???????
- boiling_point: ???????
- health_hazard: ??????
- fire_hazard: ????????
- leak_response: ????????
- storage_transport: ?????????
- first_aid: ????
- protective_measures: ????
- location: ??????????????
- max_storage: ???????????

?? JSON ???{{"items": [{{"name": "???", "cas_no": "8006-14-2", ...}}]}}
??? JSON????????"""

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
        raise HTTPException(500, f"AI ??????: {raw[:200]}")
    except Exception as e:
        raise HTTPException(500, f"AI ????: {str(e)}")


# ?? Batch create ??
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
        raise HTTPException(400, "?????????")

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
