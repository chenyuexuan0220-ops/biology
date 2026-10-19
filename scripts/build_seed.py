"""Build auditable data artifacts from the supplied implementation specification.

This is an offline authoring tool; application code never reads source documents.
"""

from pathlib import Path
import re
import json
import shutil
import yaml

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT.parent / "doc"
spec = (DOC / "生物竞赛AI学习系统_V1.0_核心知识图谱与48周课程实施规格书.md").read_text(encoding="utf-8")


def save(path, value):
    path = ROOT / "seed" / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


domain_data = [
    ("SCIENCE", "SCIENTIFIC_THINKING", "科学思维"),
    ("CELL", "CELL_BIOLOGY", "细胞生物学"),
    ("BIOCHEM", "BIOCHEMISTRY", "生物化学"),
    ("MOLECULAR", "MOLECULAR_BIOLOGY", "分子生物学"),
    ("PLANT", "PLANT_BIOLOGY", "植物学"),
    ("PLANTPHYS", "PLANT_PHYSIOLOGY", "植物生理"),
    ("MICROBE", "MICROBIOLOGY", "微生物学"),
    ("ANIMAL", "ZOOLOGY", "动物学"),
    ("ANIMALPHYS", "ANIMAL_PHYSIOLOGY", "动物生理"),
    ("GENETICS", "GENETICS", "遗传学"),
    ("EVOLUTION", "EVOLUTION", "进化"),
    ("ECOLOGY", "ECOLOGY", "生态"),
    ("EXP", "EXPERIMENTAL_BIOLOGY", "实验生物学"),
    ("DATA", "BIOINFORMATICS", "生物信息与数据"),
]
domain_map = {short: code for short, code, _ in domain_data}
save("knowledge/domains.yaml", [{"code": code, "name": name} for _, code, name in domain_data])
nodes = []
for code, name in re.findall(r"^(BIO\.[A-Z]+\.\d{3})\s+([^\r\n]+)", spec, re.M):
    if code in {n["code"] for n in nodes}:
        continue
    domain = domain_map[code.split(".")[1]]
    advanced = any(
        word in name
        for word in [
            "RNA-seq",
            "FISH",
            "Western",
            "Southern",
            "p53",
            "MDM",
            "中性理论",
            "质子",
            "缓冲",
            "膜电位",
            "流式",
        ]
    )
    nodes.append(
        {
            "code": code,
            "name": name.strip(),
            "domain": domain,
            "level": 4 if advanced else 2 if domain in {"MOLECULAR_BIOLOGY", "GENETICS", "BIOCHEMISTRY"} else 1,
            "goals": ["IBO", "RESEARCH"]
            if domain in {"EXPERIMENTAL_BIOLOGY", "BIOINFORMATICS"}
            else ["NATIONAL_LEAGUE", "NATIONAL_COMPETITION"],
            "description": f"学习目标：识别{name.strip()}，解释其基本含义，并用观察或题目证据检验理解。",
        }
    )
names = {n["name"]: n["code"] for n in nodes}
aliases = {
    "细胞": "细胞概念",
    "细胞结构": "细胞概念",
    "蒸腾": "蒸腾作用",
    "吸水": "水分吸收",
    "DNA/RNA": "DNA",
    "蛋白质": "蛋白质",
    "图表": "表格读取",
    "分类": "生物分类",
    "进化": "自然选择",
    "细胞器": "细胞质",
    "实验": "实验问题",
    "代谢": "代谢",
    "遗传": "遗传",
    "植物结构": "植物细胞",
}


def resolve(name, fallback_domain="SCIENTIFIC_THINKING"):
    name = name.strip()
    name = aliases.get(name, name)
    if name not in names:
        code = f"BIO.BRIDGE.{len(names) + 1:03d}"
        names[name] = code
        nodes.append(
            {
                "code": code,
                "name": name,
                "domain": fallback_domain,
                "level": 2,
                "description": f"规格书中列出的知识主题：{name}。详细教学内容待补充。",
                "goals": ["NATIONAL_LEAGUE"],
            }
        )
    return names[name]


chains = [
    ["细胞", "细胞膜", "扩散", "渗透", "主动运输"],
    ["细胞膜", "膜蛋白", "受体", "离子梯度", "膜电位", "静息膜电位"],
    ["植物细胞", "根", "根毛", "水分吸收", "茎", "木质部", "叶", "蒸腾作用", "水分运输"],
    ["叶", "叶绿体", "叶绿素", "光能", "光合作用"],
    ["细胞", "染色体", "DNA", "基因", "等位基因", "基因型", "表现型"],
    ["个体", "种群", "群落", "生态系统"],
    ["生态系统", "食物链", "食物网", "营养级"],
    ["假设", "变量", "自变量", "因变量", "对照组"],
    ["表格", "坐标轴", "趋势", "组间比较"],
]
edges = []
for chain in chains:
    codes = [resolve(n) for n in chain]
    edges.extend(
        {"source": a, "target": b, "relation_type": "PREREQUISITE_OF"} for a, b in zip(codes, codes[1:]) if a != b
    )

competencies = [
    ("KNOWLEDGE_UNDERSTANDING", "知识理解"),
    ("OBSERVATION", "观察"),
    ("CLASSIFICATION", "分类"),
    ("MECHANISM_REASONING", "机制推理"),
    ("CAUSAL_REASONING", "因果推理"),
    ("EXPERIMENTAL_DESIGN", "实验设计"),
    ("DATA_INTERPRETATION", "数据解释"),
    ("GRAPH_READING", "图表阅读"),
    ("QUANTITATIVE_REASONING", "定量推理"),
    ("EVOLUTIONARY_REASONING", "进化推理"),
    ("HYPOTHESIS_GENERATION", "提出假设"),
    ("SCIENTIFIC_EXPRESSION", "科学表达"),
    ("TRANSFER", "迁移"),
]
save("competencies/core.yaml", [{"code": c, "name": n} for c, n in competencies])

pages = json.loads((ROOT / "tmp/pdfs/pages.json").read_text(encoding="utf-8"))
source = "\n".join(p["text"] for p in pages)
paper_title = re.search(r"\d{4}\s*年全国中学生生物学联赛试题", source).group().replace(" ", "")
year = int(re.search(r"\d{4}", paper_title).group())
folder = f"questions/national_league/{year}"
matches = list(re.finditer(r"^\s*(\d{1,3})[.．]\s*(?=[\u4e00-\u9fffA-Za-z])", source, re.M))
parts = {
    int(match.group(1)): source[match.end() : matches[i + 1].start() if i + 1 < len(matches) else len(source)].strip()
    for i, match in enumerate(matches)
}
mapping = []
for line in spec.splitlines():
    if not re.match(r"\s+Q\d+\s{2,}", line):
        continue
    columns = re.split(r"\s{2,}", line.strip())
    if len(columns) < 6:
        continue
    number = int(columns[0][1:])
    core, prerequisites, availability, reasoning, first_year = columns[1:6]
    core_ids = [resolve(n) for n in re.split(r"[/、]", core)]
    prior_ids = [resolve(n) for n in re.split(r"[/、]", prerequisites)]
    raw = parts.get(number)
    option_matches = list(re.finditer(r"(?:^|\s)([ABCD])\.\s*", raw or ""))
    options = {
        match.group(1): raw[
            match.end() : option_matches[i + 1].start() if i + 1 < len(option_matches) else len(raw)
        ].strip()
        for i, match in enumerate(option_matches)
    }
    stem = raw[: option_matches[0].start()].strip() if option_matches else raw
    page_numbers = [p["page"] for p in pages if re.search(rf"^\s*{number}[.．]\s*", p["text"], re.M)]
    skill = (
        "EXPERIMENTAL_DESIGN"
        if "实验" in reasoning
        else "DATA_INTERPRETATION"
        if any(t in reasoning for t in ["数据", "表", "图", "曲线"])
        else "QUANTITATIVE_REASONING"
        if "定量" in reasoning
        else "MECHANISM_REASONING"
    )
    item = {
        "source_question_no": number,
        "question_type": "COMPREHENSIVE",
        "stem": stem,
        "options": options,
        "answer": None,
        "explanation": None,
        "knowledge_points": core_ids,
        "prerequisites": prior_ids,
        "competencies": [skill],
        "difficulty": {"competition": 4, "learning": 4},
        "grade_suitability": {"grade7": availability},
        "reasoning_patterns": [reasoning],
        "status": "REVIEW_REQUIRED",
        "metadata": {
            "source_pages": page_numbers,
            "raw_text": raw,
            "source_type": "PDF_TEXT_EXTRACTION",
            "answer_source": None,
            "review_notes": [
                "缺少官方答案",
                "需核对图表、跨题共用题干、排版和水印混入",
                "知识映射来自规格书，需教研确认",
            ],
            "original_format": "STATEMENT_TRUE_FALSE",
            "first_year_target": first_year,
        },
    }
    save(f"{folder}/q{number:03d}.yaml", item)
    mapping.append(
        {
            "question_no": number,
            "core": core,
            "knowledge_points": core_ids,
            "prerequisites": prior_ids,
            "reasoning": reasoning,
            "status": "REVIEW_REQUIRED",
        }
    )
save(
    f"{folder}/paper.yaml",
    {
        "code": f"national_league_{year}",
        "source_code": "national_league",
        "source_name": "全国中学生生物学联赛",
        "title": paper_title,
        "year": year,
        "metadata": {
            "expected_questions": len(mapping),
            "source_file": f"sources/{year}-national-league.pdf",
            "scoring": {
                "format": "STATEMENT_TRUE_FALSE",
                "correct_statements_to_points": {0: 0, 1: 0, 2: 0.2, 3: 1, 4: 2},
            },
        },
    },
)
save(f"{folder}/mapping.yaml", mapping)
(ROOT / "seed/sources").mkdir(exist_ok=True)
shutil.copyfile(next(DOC.glob("*.pdf")), ROOT / f"seed/sources/{year}-national-league.pdf")

units = []
unit_matches = list(re.finditer(r"^### W(\d+) ([^\n]+)", spec, re.M))
for index, match in enumerate(unit_matches):
    content = spec[
        match.end() : unit_matches[index + 1].start()
        if index + 1 < len(unit_matches)
        else spec.index("# 9. 每日任务标准")
    ].strip()
    content = re.split(r"\n## W", content)[0].strip()
    linked = [node["code"] for node in nodes if node["name"] in content or node["name"] in match.group(2)]
    units.append(
        {"sequence": int(match.group(1)), "title": match.group(2), "content": content, "knowledge_points": linked}
    )
save(
    "curriculum/foundation.yaml",
    {
        "code": "foundation_template_v1",
        "title": "生物学核心知识与竞赛桥接模板",
        "template_weeks": len(units),
        "units": units,
    },
)

# Original foundational practice, explicitly distinct from official exam source.
# Tuples: concept, skill, difficulty, stem, options, answer, explanation.
practice = [
    (
        "生物学观察",
        "OBSERVATION",
        1,
        "观察一片叶子，以下哪一项是可以直接记录的事实？",
        ["叶片边缘呈锯齿状", "叶片一定适合寒冷环境", "这株植物长得快是因为施肥", "叶片正在进行最强的光合作用"],
        "A",
        "锯齿状边缘可以直接观察；适应性、原因和光合作用强度需要额外证据。",
    ),
    (
        "细胞概念",
        "KNOWLEDGE_UNDERSTANDING",
        1,
        "下列关于细胞的描述，哪一项正确？",
        ["所有生物都只有一个细胞", "细胞是多数生物结构和功能的基本单位", "只有动物具有细胞", "细胞内部没有结构分工"],
        "B",
        "除病毒等非细胞生命形式外，细胞是生物结构和功能的基本单位。",
    ),
    (
        "假设",
        "HYPOTHESIS_GENERATION",
        1,
        "研究光照对幼苗生长的影响，哪一个假设可以通过实验检验？",
        ["幼苗很喜欢阳光", "阳光是最美的", "不同光照时长会影响幼苗高度", "所有植物都很神奇"],
        "C",
        "可检验的假设应包含可操作的因素与可测量的结果，例如光照时长与幼苗高度。",
    ),
    (
        "表格",
        "DATA_INTERPRETATION",
        1,
        "三组幼苗一周分别长高 2、4、6 厘米。仅根据数据能得出什么结论？",
        ["第三组长高最多", "第三组一定施肥最多", "第一组一定缺水", "所有植物都按固定速率生长"],
        "A",
        "数据直接支持第三组高度增量最大；不能据此推断施肥、缺水等未记录的原因。",
    ),
    (
        "生物分类",
        "CLASSIFICATION",
        1,
        "把叶片按叶缘分为全缘和锯齿状，分类时最应坚持什么？",
        ["每片叶子采用不同标准", "按采集者喜好分类", "使用相同且明确的分类标准", "先按颜色再随意按大小"],
        "C",
        "分类需要一致而明确的标准，这样不同观察者才能复核结果。",
    ),
    (
        "个体",
        "KNOWLEDGE_UNDERSTANDING",
        1,
        "生态研究中，一只生活在池塘边的青蛙属于哪个层次？",
        ["种群", "群落", "生态系统", "个体"],
        "D",
        "一只青蛙是个体；同一区域同种生物的所有个体构成种群。",
    ),
    (
        "实验问题",
        "EXPERIMENTAL_DESIGN",
        1,
        "比较有光和无光条件下幼苗生长，其他条件应该怎样设置？",
        ["水量、温度也同时改变", "尽量保持水量、温度等其他条件一致", "每组使用完全不同的植物", "不需要记录初始高度"],
        "B",
        "控制其他条件可以减少混杂，使结果更有可能反映光照的影响。",
    ),
    (
        "蛋白质",
        "MECHANISM_REASONING",
        1,
        "酶通常通过哪种作用促进生物化学反应？",
        ["改变反应的最终平衡", "永久提供反应所需能量", "降低反应的活化能", "被大量消耗成为产物"],
        "C",
        "酶降低反应活化能，加快达到平衡的速度，但不改变平衡位置。",
    ),
    (
        "生物学观察",
        "OBSERVATION",
        2,
        "两位同学观察同一批叶片得出不同的平均长度。首先应核查什么？",
        ["谁的成绩更好", "测量位置、单位与取样方式是否一致", "叶片是否认识观察者", "只保留较大的结果"],
        "B",
        "测量定义、单位和取样规则会影响结果，应先核对方法，再评估真实差异。",
    ),
    (
        "细胞概念",
        "MECHANISM_REASONING",
        2,
        "某单细胞生物能运动、摄取营养并繁殖，这说明什么？",
        [
            "单个细胞可以完成多种生命活动",
            "细胞一定没有内部结构",
            "多细胞生物的每个细胞都能独立生存",
            "运动只能由器官完成",
        ],
        "A",
        "单细胞生物以一个细胞完成多种生命活动，但不能据此推广到所有多细胞生物的细胞。",
    ),
    (
        "假设",
        "CAUSAL_REASONING",
        2,
        "某班发现浇水多的植物长得高，但这批植物也获得了更多光照。能否据此证明浇水导致长高？",
        ["能，因为二者相关", "能，只要样本是植物", "不能，光照可能是混杂因素", "不能，因为植物不需要水"],
        "C",
        "水量与光照同时变化，不能区分二者作用；需要控制光照等条件。",
    ),
    (
        "表格",
        "QUANTITATIVE_REASONING",
        2,
        "三次独立测得种子萌发率为 60%、70%、80%，这三个百分数的算术平均值是？",
        ["60%", "65%", "75%", "70%"],
        "D",
        "算术平均值为 (60+70+80)/3=70%。若样本量不同，合并萌发率需按样本量加权。",
    ),
    (
        "生物分类",
        "CLASSIFICATION",
        2,
        "蝙蝠会飞却属于哺乳动物，说明分类应优先依据什么？",
        ["是否能飞这一项特征", "多项稳定特征及亲缘关系", "生活地点", "体型大小"],
        "B",
        "同一种生活方式可在不同类群中独立出现，分类需要综合稳定特征和亲缘关系。",
    ),
    (
        "个体",
        "DATA_INTERPRETATION",
        2,
        "某地调查记录了松树、麻雀和蚂蚁。若研究它们之间的相互作用，主要属于哪个层次？",
        ["细胞", "单一个体", "群落", "只属于一个种群"],
        "C",
        "群落由一定区域内不同种群组成，种间相互作用是群落研究的重要内容。",
    ),
    (
        "实验问题",
        "EXPERIMENTAL_DESIGN",
        2,
        "评价一种肥料对幼苗的作用，为什么每组应使用多株幼苗？",
        ["增加重复以评估个体差异", "保证结论永远正确", "替代对照组", "使实验没有误差"],
        "A",
        "重复可以估计个体差异与变异，降低偶然性，但不能代替对照，也不能消除所有误差。",
    ),
    (
        "蛋白质",
        "MECHANISM_REASONING",
        2,
        "升温能加快某酶促反应，但温度过高后速率降低，合理解释是什么？",
        ["酶不再属于蛋白质", "温度不会影响结构", "高温可能破坏维持酶活性的空间结构", "反应物必然全部消失"],
        "C",
        "适度升温可增加分子运动；过高温度可能导致酶变性，降低催化能力。",
    ),
    (
        "生物学观察",
        "DATA_INTERPRETATION",
        4,
        "两组叶片长度均值分别为 5.1 和 5.3 cm，但组内变异很大。最合理的判断是？",
        ["差异必定有生物学意义", "均值不同就能证明因果", "必须结合样本量和变异评估差异证据", "只比较最大的叶片"],
        "C",
        "均值差异需要结合样本量、变异和研究设计解释，不能仅凭均值确定显著性或因果。",
    ),
    (
        "细胞概念",
        "MECHANISM_REASONING",
        4,
        "抑制线粒体 ATP 合成后，某细胞的主动运输下降。哪项对机制的推断最严谨？",
        [
            "所有跨膜运输都依赖线粒体",
            "结果支持该运输与能量供给有关，还需排除毒性等影响",
            "线粒体直接把所有物质运出细胞",
            "该结果证明细胞膜完全破裂",
        ],
        "B",
        "干预后运输下降支持能量依赖的可能，但需控制细胞活性与其他效应才能加强因果证据。",
    ),
    (
        "假设",
        "HYPOTHESIS_GENERATION",
        4,
        "假设基因 X 促进耐盐性，哪组证据最能加强因果推断？",
        [
            "只有表达量与耐盐性相关",
            "只观察一株正常植物",
            "敲除降低耐盐性，回补恢复，且有适当对照",
            "只比较两个不同物种",
        ],
        "C",
        "敲除与回补结合适当对照能较强地支持基因功能，而单纯相关不能排除混杂。",
    ),
    (
        "表格",
        "QUANTITATIVE_REASONING",
        4,
        "处理组每小时产气 12 mL，对照组 8 mL，相对于对照的增加百分比是多少？",
        ["4%", "33.3%", "50%", "150%"],
        "C",
        "相对增加为 (12-8)/8×100%=50%，分母应为对照值。",
    ),
    (
        "生物分类",
        "EVOLUTIONARY_REASONING",
        4,
        "两种远缘植物在干旱环境中都演化出厚角质层，这种相似性最可能体现什么？",
        [
            "趋同适应，不能单凭这一性状判断近缘",
            "二者必定属于同一种",
            "环境直接产生了所有适应性突变",
            "二者没有共同祖先",
        ],
        "A",
        "相似选择压力可能导致远缘类群出现相似适应性特征，需要更多性状或分子证据判断亲缘。",
    ),
    (
        "个体",
        "DATA_INTERPRETATION",
        4,
        "标记重捕调查中先标记 40 只个体，第二次捕获 50 只，其中 10 只有标记。理想假设下估算种群数量为？",
        ["100", "150", "200", "500"],
        "C",
        "若种群封闭、标记不影响捕获且充分混合，估计 N≈40×50/10=200。",
    ),
    (
        "实验问题",
        "EXPERIMENTAL_DESIGN",
        4,
        "检验光与水对植物生长的交互作用，哪种设计最合适？",
        ["只设置强光多水和弱光少水", "光照高低与水分高低交叉设置四组并重复", "所有植株条件完全相同", "只改变肥料"],
        "B",
        "双因素交叉设计能分别估计光、水的效应，并检验二者是否存在交互作用。",
    ),
    (
        "蛋白质",
        "MECHANISM_REASONING",
        4,
        "加入可逆竞争性抑制剂后，经典米氏动力学中通常如何变化？",
        ["Vmax 降低而 Km 不变", "Vmax 不变而表观 Km 增大", "Vmax 和 Km 都必定为零", "反应平衡常数必定改变"],
        "B",
        "理想竞争性抑制可被高浓度底物克服，Vmax 不变而表观 Km 增大。",
    ),
]
save(
    "questions/custom/foundation/paper.yaml",
    {
        "code": "foundation_original_v1",
        "source_code": "custom",
        "source_name": "原创基础练习",
        "title": "基础诊断与竞赛桥接练习（非官方真题）",
        "year": None,
        "metadata": {
            "expected_questions": len(practice),
            "source_type": "ORIGINAL_DEVELOPMENT_FIXTURE",
            "review_status": "DEVELOPMENT_CONTENT",
        },
    },
)
for i, (name, skill, difficulty, stem, options, answer, explanation) in enumerate(practice, 1):
    save(
        f"questions/custom/foundation/q{i:03d}.yaml",
        {
            "source_question_no": i,
            "question_type": "SINGLE_CHOICE",
            "stem": stem,
            "options": dict(zip("ABCD", options)),
            "answer": [answer],
            "explanation": explanation,
            "knowledge_points": [resolve(name)],
            "prerequisites": [],
            "competencies": [skill],
            "difficulty": {"learning": difficulty, "competition": difficulty},
            "status": "PUBLISHED",
            "metadata": {
                "source_type": "ORIGINAL_DEVELOPMENT_FIXTURE",
                "diagnostic_domain": name,
                "cognitive_level": min(difficulty, 4),
                "target_grade": 8 if difficulty < 4 else 11,
                "goals": ["NATIONAL_LEAGUE", "IBO"],
                "review_notes": ["用于软件验收的原创练习，正式教学前请教研复核"],
            },
        },
    )

save("knowledge/points.yaml", nodes)
save("knowledge/edges.yaml", list({(e["source"], e["target"]): e for e in edges}.values()))
save(
    "knowledge/resources.yaml",
    [
        {
            "knowledge_code": resolve("细胞概念"),
            "title": "从生活观察细胞",
            "level": 2,
            "min_grade": 0,
            "max_grade": 9,
            "content": "细胞是多数生物结构和功能的基本单位。洋葱表皮由许多细胞构成；细菌是单细胞生物。试着比较动物细胞和植物细胞共有的结构，说明病毒为什么不属于细胞。",
        },
        {
            "knowledge_code": resolve("细胞概念"),
            "title": "结构、功能与尺度",
            "level": 2,
            "min_grade": 10,
            "max_grade": 20,
            "content": "细胞膜建立内部环境，细胞器承担分工。细胞通过物质与能量交换维持稳态。比较真核与原核细胞的结构，讨论表面积体积比如何限制物质交换效率，并区分必要条件与充分证据。",
        },
        {
            "knowledge_code": resolve("假设"),
            "title": "写出可检验假设",
            "level": 1,
            "min_grade": 0,
            "max_grade": 20,
            "content": "可检验假设应说明变量之间的预期关系。例如：相同水量和温度下，每日光照时长会影响幼苗高度。实验前明确如何改变光照、如何测量高度，并设置重复。",
        },
    ],
)
experiments = [
    (
        "显微镜观察",
        "观察提供的洋葱表皮切片",
        "使用预制切片；玻璃载片由教师处理",
        ["调节光源与低倍镜", "观察并绘制细胞轮廓", "记录放大倍数并标注可辨认结构"],
    ),
    (
        "植物蒸腾作用",
        "比较有叶与少叶枝条的失水",
        "使用安全塑料容器，剪枝由成人完成",
        ["准备同种枝条并记录叶片数量", "保持水面覆盖和环境一致", "记录容器质量变化并比较"],
    ),
    (
        "光合作用",
        "分析教师提供的光照与产氧数据",
        "使用已有数据，不独立进行酒精加热",
        ["记录光照条件和测量单位", "绘制产氧量变化图", "区分光合与净产氧"],
    ),
    (
        "呼吸作用",
        "观察萌发种子的温度变化",
        "不密封大型容器，不食用实验材料",
        ["准备等量萌发种子与对照", "记录初始与后续温度", "分析保温和环境温度影响"],
    ),
    (
        "渗透",
        "比较不同盐水中植物组织的变化",
        "切割由成人完成，不食用实验材料",
        ["准备相同大小的植物组织", "分别放入清水和盐水并记录质量", "比较质量变化，解释水分移动"],
    ),
    (
        "酶活性",
        "分析温度影响酶活性的数据",
        "仅使用提供的实验数据",
        ["确认自变量与因变量", "绘制温度与反应速率曲线", "讨论高温对结构的影响"],
    ),
    (
        "种子萌发",
        "观察水分与萌发率",
        "避免霉变，戴手套丢弃实验材料",
        ["设置相同种子数量和温度", "控制水分条件并每日记录", "计算萌发比例与误差"],
    ),
    (
        "根向地性",
        "观察根生长方向",
        "使用透明塑料盒，不食用萌发材料",
        ["记录初始根方向", "改变种子朝向并保持其他条件", "绘制根方向随时间变化"],
    ),
    (
        "向光性",
        "观察幼苗对单侧光的生长响应",
        "不使用强激光或过热光源",
        ["设置单侧光与均匀光条件", "每天同一时段拍照记录", "比较弯曲方向与生长量"],
    ),
    (
        "叶片结构",
        "观察不同环境叶片形态",
        "不采集未知或有毒植物",
        ["选取已知安全叶片", "比较叶缘、叶脉与厚度", "区分直接观察和适应性解释"],
    ),
    (
        "生态调查",
        "记录校园生物与环境因素",
        "成人陪同，不触碰野生动物",
        ["划定安全调查范围", "记录物种与光照等环境因素", "说明取样局限"],
    ),
    (
        "群落调查",
        "用样方记录植物组成",
        "避免破坏植被",
        ["明确样方位置选择方法", "记录各样方的种类和数量", "比较样方差异"],
    ),
    (
        "种群统计",
        "利用模拟数据估计种群数量",
        "使用纸面数据",
        ["记录初次标记数与重捕数", "计算标记重捕估计值", "讨论封闭种群等假设"],
    ),
    (
        "微生物基础",
        "观察教师提供的微生物图像",
        "不培养未知环境微生物，不打开培养皿",
        ["辨认提供图像的尺度", "比较细菌与真核细胞", "讨论灭菌与无菌操作"],
    ),
    (
        "实验数据分析",
        "评价一组对照实验数据",
        "使用已知来源的数据，不编造观察",
        ["核对变量、单位与样本量", "计算均值并保留重复数据", "提出结论、局限和改进"],
    ),
]
save(
    "experiments/core.yaml",
    [
        {"code": f"EXP-{i:03d}", "title": title, "description": desc, "safety": safety, "steps": steps}
        for i, (title, desc, safety, steps) in enumerate(experiments, 1)
    ],
)
print(
    json.dumps(
        {
            "knowledge": len(nodes),
            "edges": len(edges),
            "official_questions": len(mapping),
            "practice": len(practice),
            "curriculum_weeks": len(units),
            "experiments": len(experiments),
        },
        ensure_ascii=False,
    )
)
