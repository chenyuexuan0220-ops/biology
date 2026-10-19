"""LLM boundary: receives detached dictionaries, has no repository/session access."""

import json
from typing import Protocol
import httpx
from pydantic import ValidationError, BaseModel, Field, ConfigDict
from app.config import settings, ROOT
from app.schemas import GeneratedQuestion, AIAnalysis

PROMPTS = ROOT / "prompts"


class GatewayError(Exception):
    pass


class TutorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=6000)


class Adapter(Protocol):
    async def complete(self, prompt: str, context: dict, schema: dict) -> dict: ...


class OpenAICompatibleAdapter:
    async def complete(self, prompt, context, schema):
        if not settings.llm_api_key or not settings.llm_model:
            raise GatewayError("尚未配置 LLM_API_KEY 和 LLM_MODEL；生成内容功能暂不可用")
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                response = await client.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)},
                        ],
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {"name": "biology_response", "schema": schema},
                        },
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                return json.loads(response.json()["choices"][0]["message"]["content"])
            except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
                raise GatewayError("模型服务请求失败或未返回有效 JSON") from exc


def validate_question(raw, allowed_ids, target_level):
    q = GeneratedQuestion.model_validate(raw)
    if not set(q.answer) <= set(q.options) or len(set(q.answer)) != len(q.answer):
        raise GatewayError("答案与选项不一致")
    if q.question_type in {"SINGLE_CHOICE", "TRUE_FALSE"} and len(q.answer) != 1:
        raise GatewayError("单选题答案必须唯一")
    if not set(q.knowledge_ids + q.prerequisites) <= set(allowed_ids):
        raise GatewayError("引用了知识图谱外的知识点")
    if abs(q.learning_difficulty - target_level) > 2:
        raise GatewayError("生成难度与目标能力不匹配")
    if len(set(q.options.values())) != len(q.options):
        raise GatewayError("选项重复")
    return q


class Gateway:
    def __init__(self, adapter: Adapter | None = None):
        self.adapter = adapter or OpenAICompatibleAdapter()

    async def tutor(self, context, message, level):
        if not settings.llm_api_key or not settings.llm_model:
            return tutor_hint(context, message, level)
        # No standard answer/analysis enters the provider before the last hint level.
        detached = {key: value for key, value in context.items() if key != "explanation" or level == 4}
        prompt = (PROMPTS / "tutor.v1.txt").read_text(encoding="utf-8")
        raw = await self.adapter.complete(
            prompt,
            {"learning_context": detached, "message": message, "hint_level": level},
            TutorOutput.model_json_schema(),
        )
        try:
            output = TutorOutput.model_validate(raw)
        except ValidationError as exc:
            raise GatewayError("辅导回复未通过结构验证") from exc
        return {"message": output.message, "hint_level": level, "mode": "LLM", "label": "AI 学习导师 · 生成回复"}

    async def generate(self, purpose, context):
        schema = GeneratedQuestion if purpose == "generate" else AIAnalysis
        prompt = (PROMPTS / "content.v1.txt").read_text(encoding="utf-8")
        try:
            raw = await self.adapter.complete(prompt, {"purpose": purpose, **context}, schema.model_json_schema())
            if purpose == "generate":
                result = validate_question(
                    raw, context["allowed_knowledge_ids"], int(context["request"]["target_biology_level"][1])
                )
            else:
                result = AIAnalysis.model_validate(raw)
                if not set(result.knowledge_ids + result.prerequisites) <= set(context["allowed_knowledge_ids"]):
                    raise GatewayError("分析引用了知识图谱外的节点")
            return result.model_dump()
        except ValidationError as exc:
            raise GatewayError("模型输出未通过结构校验") from exc


def tutor_hint(context, message, level):
    """Deterministic Socratic fallback, clearly identified to the user, never claims to be an LLM."""
    knowledge = context.get("knowledge_names") or ["题目涉及的基本概念"]
    name = "、".join(knowledge[:3])
    if level == 0:
        text = f"先说说你的想法：关于{name}，题目给了哪些已知条件？哪些是观察，哪些是你的推断？"
    elif level == 1:
        text = f"概念提醒：先回顾{name}的定义。用一句话说明结构与功能，或自变量与因变量的关系。"
    elif level == 2:
        text = "试着逐项核对：这个陈述需要哪些条件？条件是否在题干中成立？留意“总是”“唯一”等绝对表述。"
    elif level == 3:
        text = "把推理写成三步：题干证据 → 生物学机制 → 对选项的预测。实验题还要比较对照组，判断是否只改变了一个因素。"
    else:
        text = context.get("explanation") or "目前没有已审核的完整解析。请将你的推理记录下来，与教师一起核对。"
    if context.get("last_error"):
        text += " 上次作答存在知识或概念缺口，请说明你最不确定的一步。"
    return {"message": text, "hint_level": level, "mode": "RULE_BASED", "label": "规则导师（未调用大模型）"}
