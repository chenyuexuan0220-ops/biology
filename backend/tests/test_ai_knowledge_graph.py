import asyncio

import pytest

from app.ai.gateway import GatewayError
from app.ai.knowledge_graph import analyze_sections, validate_batch
from app.services.source_drafts import textbook_draft
import yaml


KNOWLEDGE = [
    {"code": "BIO.CELL.004", "name": "细胞膜"},
    {"code": "BIO.CELL.013", "name": "扩散"},
]
SECTIONS = [{"title": "第1章 物质运输", "content": "细胞膜控制物质交换，扩散沿浓度梯度进行。"}]


class FakeAdapter:
    async def complete(self, prompt, context, schema):
        assert "未经信任" in prompt
        assert {item["code"] for item in context["catalog"]} == {item["code"] for item in KNOWLEDGE}
        return {"sections": [{
            "section": 1,
            "existing": [
                {"code": "BIO.CELL.004", "evidence": "细胞膜控制物质交换"},
                {"code": "BIO.CELL.013", "evidence": "扩散沿浓度梯度进行"},
            ],
            "new_concepts": [{"name": "浓度梯度", "evidence": "浓度梯度进行"}],
            "relations": [{"source": "BIO.CELL.004", "target": "BIO.CELL.013",
                           "relation_type": "RELATED_TO", "evidence": "物质交换，扩散"}],
        }]}


def test_ai_mappings_become_review_drafts():
    result = asyncio.run(analyze_sections(SECTIONS, KNOWLEDGE, FakeAdapter()))
    files = textbook_draft("第1章 物质运输\n细胞膜控制物质交换，扩散沿浓度梯度进行。", KNOWLEDGE,
                           "biology.docx", result)
    resources = yaml.safe_load(files["resources.yaml"])
    review = yaml.safe_load(files["knowledge_review.yaml"])
    assert {item["knowledge_code"] for item in resources} == {"BIO.CELL.004", "BIO.CELL.013"}
    assert review["sections"][0]["method"] == "AI_ASSISTED"
    assert review["new_knowledge_candidates"][0]["status"] == "REVIEW_REQUIRED"
    assert review["relation_candidates"][0]["evidence"] == "物质交换，扩散"


def test_long_section_is_analyzed_beyond_the_beginning():
    class TailAdapter:
        async def complete(self, prompt, context, schema):
            return {"sections": [
                {"section": item["section"],
                 "existing": ([{"code": "BIO.CELL.013", "evidence": "扩散沿浓度梯度进行"}]
                              if "扩散沿浓度梯度进行" in item["content"] else []),
                 "new_concepts": [], "relations": []}
                for item in context["sections"]
            ]}

    sections = [{"title": "长章节", "content": "甲" * 2500 + "扩散沿浓度梯度进行"}]
    result = asyncio.run(analyze_sections(sections, KNOWLEDGE, TailAdapter()))
    assert [item["code"] for item in result[0]["existing"]] == ["BIO.CELL.013"]


def test_ai_rejects_cyclic_prerequisite_proposal():
    class CycleAdapter:
        async def complete(self, prompt, context, schema):
            return {"sections": [{
                "section": 1,
                "existing": [
                    {"code": "BIO.CELL.004", "evidence": "细胞膜控制物质交换"},
                    {"code": "BIO.CELL.013", "evidence": "扩散沿浓度梯度进行"},
                ],
                "new_concepts": [],
                "relations": [{"source": "BIO.CELL.013", "target": "BIO.CELL.004",
                               "relation_type": "PREREQUISITE_OF", "evidence": "物质交换，扩散"}],
            }]}

    with pytest.raises(GatewayError, match="循环"):
        asyncio.run(analyze_sections(SECTIONS, KNOWLEDGE, CycleAdapter(),
                                     existing_edges=[("BIO.CELL.004", "BIO.CELL.013")]))


@pytest.mark.parametrize("change", [
    {"existing": [{"code": "BIO.FAKE.001", "evidence": "细胞膜控制物质交换"}]},
    {"existing": [{"code": "BIO.CELL.004", "evidence": "不存在于教材的证据"}]},
    {"relations": [{"source": "BIO.CELL.004", "target": "BIO.FAKE.001",
                    "relation_type": "PREREQUISITE_OF", "evidence": "物质交换，扩散"}]},
])
def test_ai_rejects_fabricated_codes_evidence_and_edges(change):
    raw = {"sections": [{"section": 1, "existing": [{"code": "BIO.CELL.004", "evidence": "细胞膜控制物质交换"}],
                         "new_concepts": [], "relations": [], **change}]}
    with pytest.raises(GatewayError):
        validate_batch(raw, SECTIONS, KNOWLEDGE)
