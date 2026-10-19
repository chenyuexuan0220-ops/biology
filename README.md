# 知生 · 生物竞赛 AI 学习系统 V1.2.1

依据 `doc/生物竞赛AI学习系统_V1.2_Codex可执行开发文档.md` 开发的可运行核心闭环。V1.2 优先，V1.0 文档用于补充知识、课程与题目映射。代码和运行数据均放在本目录。

已实现多用户/多学生、角色授权、学习上下文、知识前置 DAG、题库、诊断、证据驱动掌握度、复习与可解释计划，以及 Next.js 中文工作台。当前是开发版，不代表所有教研内容已达到正式发布标准。

## 启动

环境：Python 3.12+，Node.js 22+（本机已用 Node 24 验证）。从 `code` 目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e '.[dev]'
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python scripts\seed.py
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一终端启动前端：

```powershell
cd frontend
npm ci
npm run dev
```

或使用 `scripts/start-local.ps1`（自动识别当前电脑附带的 Node 24；安装依赖、迁移、导入后以隐藏窗口启动本地服务，日志保存在 `tmp/`）。停止使用 `scripts/stop-local.ps1`，仅停止该启动脚本记录的服务进程。

- 页面：[http://localhost:3000](http://localhost:3000)
- API 文档：[http://localhost:8000/docs](http://localhost:8000/docs)
- 健康检查：[http://localhost:8000/health](http://localhost:8000/health)

首次使用：注册家长账号 → 添加学生 → 设置年级/实际能力/目标 → 能力诊断 → 生成学习计划 → 学习或答题 → 查看画像与错题 → 重新规划。

默认本地数据库为 SQLite，仅用于便捷开发和自动化测试。正式部署使用 PostgreSQL。没有 `.env` 时 JWT 密钥只在当前进程有效，重启后需要重新登录；启动脚本会创建带随机持久密钥的本地 `.env`。

## Docker / PostgreSQL

复制 `.env.example` 为 `.env`，将 `JWT_SECRET` 改为足够长的随机字符串，然后：

```sh
docker compose up --build -d
```

Compose 使用 PostgreSQL 16；后端启动时通过 Alembic 迁移后导入幂等 seed。前后端端口默认只绑定本机。远程部署需配置真实访问地址、CORS、TLS 和数据库凭据。

当前电脑没有 Docker，未在此机运行容器。CI 配置包含 PostgreSQL 16 迁移、seed 与 API 冒烟检查。

## 数据与内容状态

| 数据 | 当前内容 |
| --- | --- |
| 知识图谱 | 364 节点、14 领域、40 条前置关系；节点编码来源于规格书，桥接主题另有稳定编码 |
| 能力 | 13 种能力，独立证据和画像 |
| 原卷 | 72 道题，全部保留题号、PDF 页码、原始文本与知识映射 |
| 原卷状态 | `REVIEW_REQUIRED`；PDF 没有附官方答案，因此答案/解析为 null；图表、共用题干、水印与映射待人工核对 |
| 开发练习 | 24 道原创基础/进阶题，用于软件验收；不是官方真题，正式教学前仍建议教研复核 |
| 课程 | 48 周数据模板；已补充“细胞与物质运输”12 个待审核版本和“动物结构与组织”3 个待审核版本 |
| 实验 | 15 个观察、实验或数据分析任务，含步骤、安全要求和学生观察记录 |

源 PDF 保存在 `seed/sources/`，管理员可在页面中预览。原卷是四个陈述分别判断正误；答案采用 `A:T`、`B:F` 等编码。题目审核后才会对学生开放。

**未完成的教研工作**：官方答案核对、全部图表与跨题背景拆分、动物组织之后其余动物知识点的分层课文、全量前置关系复核、实验设计主观评分量表。当前知识图谱和课程模板是内容底座，并非完整教材。新增课程默认保持 REVIEW_REQUIRED，需管理员审核后发布。

## AI 与审核

在 `.env` 设置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，支持兼容 Chat Completions 和 JSON Schema 的服务。密钥仅保留在后端。

- AI Gateway 接收脱离数据库的字典，不持有 DB Session；Prompt 保存在 `prompts/*.v1.txt`。
- 题目生成/分析经过 Pydantic 和规则检查，写为待审核草稿。
- 管理员“审核通过”与“发布”分开执行；生成内容不能直接发布。
- Tutor 从 H0 到 H4 逐级提示，H4 之前不向模型提供标准解析。
- 未配置模型时显示**规则导师**，提供固定的苏格拉底式引导；不会伪装为真实模型回复。真实模型调用需配置后验证。
- 软件可验证结构、引用、答案选项和难度约束；生物学正确性仍需人工审核。

管理员由本地操作者显式创建/授权，公开注册不会自动成为管理员：

```powershell
.\.venv\Scripts\python scripts\create_admin.py admin@example.com
```

若邮箱未注册，脚本交互式读取密码；已注册时直接授权，并写入审计日志。

忘记密码时，在运行后端的本机上执行 `.\.venv\Scripts\python scripts\reset_password.py 账号邮箱`，按提示输入并确认新密码（10–128 个字符）。该命令只重置已有账号的密码，不更改管理员权限或学生数据。

## 关键约束

- 所有学生读写先验证 `user_students` 关系。VIEWER 只读，OWNER 可授权，TEACHER/PARENT 可学习操作。管理员内容权限不自动赋予学生数据读取权。
- 作答在服务端评分。`QUESTION_ANSWER` 和掌握度变更不能通过通用事件接口伪造。
- `event_id` 全局唯一，同一输入重放返回原记录；不同输入复用 ID 返回 409。
- 掌握度是 0–1 分值，文档的 +8 对应 +0.08。五个认知维度独立更新后按文档权重加权；不会由任务完成率冒充掌握度。
- 掌握度/报告/推荐支持 `as_of`；历史读取从截止时间内证据重算，不读取当前掌握度缓存。
- 前置知识掌握度低于 0.4 时阻止推荐后继；难度差超过 2 时只安排基础桥接。
- 每个任务包含推荐原因、知识缺口、前置理由、目标理由、能力理由和推荐时机。
- 切换上下文保留历史，旧计划标记被替代；计划重算保留历史计划。
- 当前自适应模型为启发式 MVP，统计置信度与复习间隔需要后续用真实教学数据校准。

## 测试与维护

```powershell
.\.venv\Scripts\pytest -q
.\.venv\Scripts\ruff check backend scripts migrations
cd frontend
npm run typecheck
npm run build
```

测试覆盖多学生闭环、等级/年级/目标差异、前置与难度约束、事件重放、授权、AI 门禁、历史隔离、seed 幂等与新增年份。详见 `docs/VERIFICATION.md`。

新增题库：在 `seed/questions/<赛事>/<年份>/` 增加 `paper.yaml` 与 `qNNN.yaml` 后重新运行 `scripts/seed.py`。无需改业务模型。已有数据不会被 seed 覆盖，避免覆盖人工审核。

管理员可在“内容审核”页面直接上传文本型 PDF 或 `.docx` 教材/试卷（单文件 20 MB，PDF 最多 250 页）。系统按可识别的章节标题拆分教材，依据已有知识点名称在章节标题和正文中的出现情况生成多个候选映射，不再将整份教材绑定到一个知识点。试卷逐题做同样的候选匹配。下载的 ZIP 含 `knowledge_review.yaml`，列出每节或每题的匹配证据、未匹配章节标题和同节共现的 `RELATED_TO` 关系建议。共现不等于前置依赖；系统不会自动建立 `PREREQUISITE_OF` 关系，也不会把新概念直接写入图谱。当前匹配是可解释的词面规则，不具备同义词和语义推断能力，须人工核对。

上传时可勾选“使用 AI 辅助识别”。先在 `.env` 配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 并重启后端；模型服务需支持兼容 Chat Completions 的 JSON Schema 输出。AI 模式将长章节切成有少量重叠的文本片段，再合并回原章节；单次最多处理 40 个片段，每批分析 4 个片段，超出时需按章分批上传。文本会发送至所配置的模型服务。当前 364 个知识点会作为候选目录一并提供给模型，以便识别同义表达。模型可以建议已有节点、新概念和 `RELATED_TO` / `PREREQUISITE_OF` 关系，但必须引用逐字出现在原文中的证据；系统会校验编码、证据和关系端点。通过校验的结果也只生成待审核 YAML，不写入正式图谱。未配置模型时不勾选该选项，继续使用词面规则。

教材生成 `resources.yaml` 格式，试卷生成 `paper.yaml` 和逐题 `qNNN.yaml`。无匹配的教材章节不会进入 `resources.yaml`，无匹配的题目会保留空的 `knowledge_points`，均需先在审核文件中处理。扫描 PDF 需先 OCR，旧版 `.doc` 需另存为 `.docx`。自动提取不判断答案或生物学正确性；请核对图表、跨页题干、知识映射与答案。教材资源需合并进 `seed/knowledge/resources.yaml`；经确认的新知识点和关系分别整理到 `seed/knowledge/points.yaml`、`seed/knowledge/edges.yaml`。试卷文件放入独立的 `seed/questions/<来源>/<年份>/` 目录，再运行 `scripts/seed.py`。新增题目默认待审核，管理员审核和发布后学生才可见。

内容提取作者工具：`scripts/extract_source.py` 提取 PDF；`scripts/build_seed.py` 根据随附规格书生成初始 YAML（已有编辑内容请先备份，作者工具会重新生成初始数据）。日常运行只需 `scripts/seed.py`，不依赖 `doc` 目录。

目录说明与已完成/待完善项目见 [ARCHITECTURE.md](ARCHITECTURE.md)、[TASKS.md](TASKS.md)、[docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md)。
