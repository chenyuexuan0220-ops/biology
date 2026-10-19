"""Author the first animal-structure lesson as review-only content."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
TIERS = [("INTRO", 0, 1, "入门理解"), ("APPLICATION", 2, 3, "情境应用"), ("COMPETITION", 4, 7, "竞赛推理")]

COMMON = {
    "code": "BIO.ANIMAL.001", "name": "动物组织", "prior": "BIO.CELL.001",
    "diagram": "TISSUES", "labels": ["上皮组织", "结缔组织", "肌肉组织", "神经组织"],
    "caption": "四类动物组织的概念示意：细胞形态、排列和细胞外基质不同，结构差异与功能分工相关；图示不按组织切片比例绘制。",
    "misconceptions": [
        ("一种组织只能由一种细胞组成。", "组织通常由形态和功能相近的细胞以及细胞外成分共同构成，不能只看单个细胞。"),
        ("组织的名称直接等于它所在的器官。", "组织是器官的组成层次；一个器官通常含有多种组织，名称不能互相替代。"),
    ],
}

MATERIAL = {
    "INTRO": {
        "objectives": ["说出上皮、结缔、肌肉和神经组织的基本功能", "根据排列和形态线索初步辨认四类动物组织"],
        "sections": [
            ("从细胞到组织", "多细胞动物的细胞会分工协作。形态和功能相近的细胞，与周围的细胞外成分共同形成组织；多种组织进一步组成器官。组织不是把相邻细胞简单堆在一起，而是具有相对稳定的结构和功能关系。"),
            ("四类组织各做什么", "上皮组织覆盖体表或衬在体内管腔表面，常有保护、吸收和分泌作用；结缔组织支持、连接并运输，血液、骨和脂肪都属于广义结缔组织；肌肉组织收缩产生力量；神经组织接受、传递和处理信息。"),
            ("先看形态，再联系功能", "观察组织图像时，可以先看细胞是否排列紧密、细胞外基质多少、是否呈长纤维或具有突起，再结合所在位置和功能判断。单凭颜色或一处模糊轮廓不能下结论，切片方向和染色方法都会影响外观。"),
        ],
        "example": ("皮肤表面和皮下脂肪为什么不是同一种组织？", "皮肤表面细胞排列紧密，形成屏障，符合上皮组织特征；皮下脂肪细胞之间有较多细胞外成分并储存能量，属于结缔组织。一个器官可以同时含有多种组织。"),
        "questions": [
            ("哪类组织的细胞通常排列较紧密，覆盖体表或衬里？", ["上皮组织", "结缔组织", "肌肉组织", "神经组织"], "A", "上皮组织形成覆盖层或衬里，细胞通常排列较紧密，可承担保护、吸收或分泌。", 0, "s1"),
            ("血液在组织分类中通常归入哪一类？", ["上皮组织", "结缔组织", "肌肉组织", "神经组织"], "B", "血液含有细胞和液体细胞外基质，具有运输和调节作用，通常归入结缔组织。", 1, "s2"),
            ("肌肉组织最直接的共同特征是什么？", ["产生收缩", "形成角质层", "储存遗传信息", "传递视觉光线"], "A", "肌肉组织的细胞能够收缩，收缩产生运动或推动体内物质。", 0, "s2"),
            ("辨认组织切片时，较稳妥的做法是？", ["只看颜色", "只看一个细胞", "结合形态、位置和功能线索", "看到细胞核就判定为神经组织"], "C", "组织识别需要综合排列、细胞外基质、位置和功能等证据，不能依赖单一外观线索。", 1, "s3"),
        ],
    },
    "APPLICATION": {
        "objectives": ["用结构特征比较四类动物组织", "解释组织结构与器官功能之间的联系"],
        "sections": [
            ("结构线索不是标签", "上皮组织常见连续细胞层和明显的顶端、基底方向；结缔组织的细胞外基质通常更突出，成分可呈液态、胶状或固态；肌肉组织常见平行排列的细长细胞；神经组织常见胞体和突起。实际样本可能混合多种组织，不能把示意图当成所有切片的固定外观。"),
            ("组织如何组成器官", "小肠壁同时包含上皮、结缔、平滑肌和神经组织：上皮负责吸收和屏障，结缔组织提供支持与血管通路，平滑肌推动内容物，神经组织参与调节。解释器官功能时，应把各组织的作用连成过程，而不是只列出组织名称。"),
            ("用证据区分相近样本", "如果样本细胞成层排列、靠近自由表面且细胞外基质少，支持上皮判断；如果细胞分散在大量基质中，支持结缔组织判断。若要区分肌肉和神经组织，还需观察条纹或突起、收缩标记以及神经元和胶质细胞的组合等信息。"),
        ],
        "example": ("小肠蠕动变弱，哪些组织功能值得优先检查？", "应优先考虑平滑肌的收缩能力，也要考虑神经组织调节和能量供应。小肠功能是多组织协作的结果，不能看到运动减弱就只归因于上皮吸收异常。"),
        "questions": [
            ("某切片细胞排列成连续单层，靠近腔面，细胞外基质少。最符合哪类组织？", ["上皮组织", "结缔组织", "肌肉组织", "神经组织"], "A", "连续细胞层、靠近腔面和较少基质是衬里上皮的典型线索。", 1, "s1"),
            ("小肠壁中，推动食物沿管道移动的主要组织是？", ["上皮组织", "结缔组织", "平滑肌组织", "神经组织"], "C", "平滑肌的节律性收缩可推动管腔内容物；神经组织参与调节但本身不直接产生主要推力。", 1, "s2"),
            ("某样本细胞分散在大量胶状基质中，最支持什么判断？", ["上皮组织", "结缔组织", "肌肉组织", "神经组织"], "B", "细胞外基质丰富且细胞相对分散，是结缔组织的重要结构线索。", 1, "s3"),
            ("解释一个器官的功能时，最好的表达是？", ["只写器官名称", "把多种组织的结构和作用连成过程", "只依据染色颜色", "把所有细胞视为相同"], "B", "器官功能来自多种组织协作，应说明结构如何支持过程并保留证据边界。", 2, "s2"),
        ],
    },
    "COMPETITION": {
        "objectives": ["从组织结构提出可检验的功能假设", "评价组织图像与功能实验中的证据边界"],
        "sections": [
            ("组织是结构与功能的中间层", "竞赛题中常把组织学图像、器官功能和实验数据放在一起。应先区分观察事实与机制解释：细胞排列紧密是观察，形成屏障是解释，通透性下降是需要测量的结果。一个组织特征可能支持多个机制，不能把相关现象写成唯一因果。"),
            ("细胞外基质与力学功能", "结缔组织的细胞外基质并非填充物而已，其胶原、弹性纤维、矿化成分和含水量会影响抗拉、弹性、硬度与扩散。比较软骨、骨、肌腱或血液时，要明确基质组成和细胞位置，再联系承重、连接或运输功能。"),
            ("组织图像和实验要配对", "若想证明某组织特征导致屏障功能增强，可比较不同处理后的通透性、细胞连接蛋白定位和组织完整性，并设置等量、染色和损伤对照。若肌肉收缩减弱，还需测量活性、钙信号和能量状态，排除细胞死亡或非特异损伤。"),
        ],
        "example": ("某处理让上皮层看起来更紧密，同时示踪物通过量下降，如何写出谨慎结论？", "可以说处理与上皮屏障增强和示踪物通透性下降相关；若要支持紧密连接导致变化，还需检测连接蛋白、细胞活性和可逆性，并排除组织厚度或损伤差异。"),
        "questions": [
            ("观察到上皮细胞排列更紧密且示踪物通过量下降，最谨慎的结论是？", ["已证明紧密连接是唯一原因", "两者相关，仍需机制和损伤对照", "说明所有物质都不能通过", "说明样本一定是结缔组织"], "B", "图像与通透性变化支持相关关系，但仍需连接蛋白、活性和损伤等证据来讨论机制。", 3, "s1"),
            ("骨组织能承受压力，最应关注哪项结构证据？", ["只有细胞核颜色", "矿化细胞外基质及其排列", "是否有神经突起", "是否覆盖体表"], "B", "骨的矿化细胞外基质及其空间排列与硬度和承重功能有关。", 2, "s2"),
            ("肌肉收缩减弱时，哪组补充测量最能排除非特异损伤？", ["只拍一张照片", "细胞活性、钙信号和能量状态", "只改变显微镜颜色", "删除异常值"], "B", "活性、钙信号和能量状态有助于区分收缩机制受影响与细胞普遍受损。", 3, "s3"),
            ("同一器官中存在多类组织，最合理的推论是？", ["组织之间没有关系", "器官功能可能来自多层次协作", "只有占面积最大的组织有作用", "组织分类不再有意义"], "B", "器官功能常由不同组织在空间和时间上的协作产生，组织分类仍能帮助拆解机制。", 2, "s2"),
        ],
    },
}

def document(tier, name):
    material = MATERIAL[tier]
    checks = []
    for index, (stem, options, answer, explanation, cognitive, revisit) in enumerate(material["questions"], 1):
        checks.append({"id": f"q{index}", "stem": stem, "options": dict(zip("ABCD", options)), "answer": answer,
                       "explanation": explanation, "cognitive_level": cognitive, "competency_code": "KNOWLEDGE_UNDERSTANDING" if cognitive < 2 else "MECHANISM_REASONING",
                       "revisit_section": revisit, "prerequisite_code": COMMON["prior"] if index == 4 else None, "evidence_kind": "TRANSFER" if cognitive >= 2 else "STANDARD"})
    return {"title": f"动物组织：{name}", "summary": "从四类动物组织的结构特征出发，连接组织、器官与功能，练习用图像和实验证据解释生物学现象。",
            "objectives": material["objectives"], "estimated_minutes": 25 if tier == "INTRO" else 30 if tier == "APPLICATION" else 40,
            "prerequisites": [COMMON["prior"]], "sections": [{"id": f"s{i}", "title": title, "text": text} for i, (title, text) in enumerate(material["sections"], 1)],
            "diagram": {"kind": COMMON["diagram"], "labels": COMMON["labels"], "caption": COMMON["caption"]},
            "examples": [{"prompt": material["example"][0], "reasoning": material["example"][1]}],
            "misconceptions": [{"claim": a, "correction": b} for a, b in COMMON["misconceptions"]], "checks": checks,
            "pass_ratio": 0.8, "adaptations": {"junior": "先按排列、基质和位置找线索，再用四类组织的基本功能核对判断。", "senior": "区分观察、相关和因果；解释组织结构如何影响器官功能，并写出仍需补充的对照证据。"},
            "sources": ["OpenStax Biology 2e，第 33 章 Animal Form and Function；https://openstax.org/details/books/biology-2e", "本项目原创分层讲解与检测；待人工核对，非官方竞赛试题。"]}

def main():
    rows = []
    for tier, min_level, max_level, name in TIERS:
        code = f"animal-structure:{COMMON['code']}:{tier}"
        rows.append({"code": code, "unit_code": "animal-structure", "unit_title": "动物结构与组织", "sequence": 1,
                     "knowledge_code": COMMON["code"], "tier": tier, "min_level": min_level, "max_level": max_level, "version": 1,
                     "document": document(tier, name)})
    path = ROOT / "seed" / "lessons" / "animal_tissues.yaml"
    path.write_text(yaml.safe_dump(rows, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Authored {len(rows)} review drafts: {path}")

if __name__ == "__main__":
    main()
