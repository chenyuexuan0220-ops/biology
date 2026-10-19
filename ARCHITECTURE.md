# 架构

Next.js / React / TypeScript / Tailwind / TanStack Query / Zod → FastAPI / Pydantic → 应用服务 → SQLAlchemy → PostgreSQL 16。

本地与测试可使用 SQLite。所有建表迁移由 `migrations` 下的 Alembic revision 执行，应用启动不调用 `create_all`。

## 模块

- `backend/app/api/routes.py`：认证、学生范围、知识、题目、学习、内容审核 API。
- `security.py`：Argon2 密码、JWT、学生 scope、当前上下文和任务归属验证。
- `services/learning.py`：诊断抽题、服务器评分、答题记录。
- `services/mastery.py`：证据增量、五维画像、能力画像、复习时间与历史重放；唯一掌握度写入入口。
- `planners/adaptive.py`：前置图筛选、七项加权排序、难度桥接、时间预算和计划保存。
- `services/seed.py`：Schema 校验、DAG 校验、稳定 UUID、可重复导入。
- `services/content.py`：AI 草稿应用服务，人工审核与发布。
- `ai/gateway.py`：无数据库依赖的 Adapter 接口、兼容 LLM 适配器、Schema/规则门禁、Tutor。
- `frontend/app`：中文学习工作台与管理员教研工作台。

## 事务与隔离

每个请求使用一个数据库事务。私有操作先检查 UserStudent，再核查 Context/Task/Diagnostic/TutorSession 的学生归属。PostgreSQL 使用学生行锁序列化同一学生的作答和计划写入；唯一事件键是幂等的最终约束。

学习事件、作答、证据与画像缓存同事务写入。普通客户端只能记录非评分行为，不能传入正确性或自定义证据分数。学生无删除事件、证据和审计记录的接口。

## 历史计算

历史画像只使用 `LearningEvent.created_at <= as_of` 且 `Evidence.created_at <= as_of` 的记录；上下文激活写入审计日志，历史规划按激活时间选择上下文。未来错误和未来作答不参与历史排名。图谱内容目前保留创建时间，尚未提供完整的内容版本回溯；历史教育内容修订的再现能力属于后续完善项。

## 内容发布

真题 PDF 文本和知识映射都是待审核导入材料。AI 内容默认 REVIEW_REQUIRED → 管理员 REVIEWED → 管理员 PUBLISHED。AI 仅返回脱离数据库的结构化内容，应用服务负责持久化。Tutor 对话不被发布为教材。

## 当前边界

诊断、掌握度与规划为可解释规则引擎；不宣称经过真实学生数据验证的能力测量精度。课程目前以周模板与少量完整学习资源提供内容，后续需持续补充教研内容。暂无后台任务队列、模型流式输出、完整内容版本库、运营级可观测性和高并发压测结论。
