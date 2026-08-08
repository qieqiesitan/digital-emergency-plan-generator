"""LLM Reranker —— 对 scorer 产出 Top-30 做最终精排，选出 5-8 条最相关条文。

设计考量：
- 复用用户已有 AI 配置，temperature=0, max_tokens=500
- 每章仅 1 次 rerank call，30 条候选 batch 传入
- 失败时静默回退到 scorer 原始排序
"""

import json
import logging
import re

from app.services.llm_client import decrypt_api_key, llm_chat_completion, LLMError

logger = logging.getLogger(__name__)

RERANK_PROMPT = """你是一位安全生产法规专家。以下是 30 条候选法规条文，请根据章节标题选择最相关的 5-8 条。

【章节标题】{section_title}
【预案类型】{plan_type}

【候选条文】
{candidates_text}

请选出与本章节内容最直接相关的 5-8 条条文。选择标准：
1. 条文内容直接涉及本章节要讨论的主题
2. 条文规定了本章节必须覆盖的要求/程序/标准
3. 优先选择提出了具体指标、阈值、流程的条文
4. 排除仅在编制依据中需要列出的法规名称类条文

只返回 JSON 数组，包含选中的 article_id，按相关性从高到低排列：
["art_xxx_xxx", "art_yyy_yyy", ...]"""


class LLMReranker:
    """使用 LLM 对候选条文做最终精排。"""

    def __init__(self, ai_config=None):
        self.ai_config = ai_config

    async def rerank(
        self,
        candidates: list,
        section_title: str,
        section_text: str = "",
        plan_type: str = "",
    ) -> list[str]:
        """
        精排候选条文，返回按相关性排序的 article_id 列表。

        candidates: list[ScoredArticle]
        返回: list[str] article_id 列表
        失败时回退到 scorer 原始排序。
        """
        if len(candidates) <= 8:
            return [c.candidate.id for c in candidates]

        if not self.ai_config:
            logger.debug("LLM reranker: no AI config, falling back to scorer order")
            return [c.candidate.id for c in candidates[:8]]

        # 构建候选列表
        cand_lines = []
        for i, sa in enumerate(candidates[:30], 1):
            c = sa.candidate
            cand_lines.append(
                f"[{i}] ID: {c.id} | {c.regulation_name} {c.article_number}\n"
                f"    条文: {c.article_text[:150].replace(chr(10), ' ')}..."
            )

        prompt = RERANK_PROMPT.format(
            section_title=section_title,
            section_text=section_text or section_title,
            plan_type=plan_type,
            candidates_text="\n".join(cand_lines),
        )

        try:
            response = await self._call_llm(prompt)
            # 提取 JSON 数组
            ids = self._parse_response(response)
            if ids and len(ids) >= 3:
                logger.info(
                    "LLM rerank: %d candidates -> %d selected",
                    len(candidates),
                    len(ids),
                )
                return ids[:8]
        except Exception as e:
            logger.warning("LLM rerank failed, falling back to scorer order: %s", e)

        return [c.candidate.id for c in candidates[:8]]

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM API。"""
        try:
            decrypt_api_key(self.ai_config.api_key_encrypted)
        except Exception:
            raise Exception("API Key 解密失败")

        messages = [
            {
                "role": "system",
                "content": "你是一个精确的 JSON 数组生成器。只输出 JSON 数组，不要解释。",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            data = await llm_chat_completion(
                messages, self.ai_config, stream=False, timeout=30,
                include_top_p=False,
                payload_overrides={"temperature": 0, "max_tokens": 500},
            )
            return data["choices"][0]["message"]["content"]
        except LLMError as e:
            raise Exception(f"LLM API error: HTTP {e.status_code}")

    def _parse_response(self, text: str) -> list[str]:
        """从 LLM 响应中提取 article_id 列表。"""
        # 尝试直接解析
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # 提取 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?[\s]*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(1).strip())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # 提取第一个 [ ... ] 数组
        m = re.search(r"\[.*?\]", text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(0))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        logger.warning("LLM reranker: could not parse response: %s", text[:200])
        return []
