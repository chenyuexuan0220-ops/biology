# 验证记录

## 自动化

在 Windows 本地环境执行：

```text
22 passed, 2 warnings in 16.17s
ruff check backend scripts migrations: All checks passed
frontend TypeScript: passed
frontend Next.js production build (webpack): passed
```

测试覆盖多学生闭环、年级/能力/目标差异、前置知识门禁、难度桥接、事件重放、学生范围授权、VIEWER 只读、历史 `as_of`、AI 结构门禁、AI 发布审批、seed 幂等、扩展年份、导师逐级提示、题目脱敏、72 题导入和 DAG 循环检查。

## 浏览器冒烟

使用 Playwright 技能启动 `http://localhost:3000`，验证：

- 注册家长账号；
- 创建学生；
- 设置 G7 / L1 / NATIONAL_LEAGUE；
- 生成今日学习计划；
- 桌面宽度 1440×1000 页面无裁切，hero、任务、掌握度和实验入口可见；
- 题目练习页展示 24 道已发布原创练习并隐藏答案，任务可打开；
- 页面控制台只报告开发服务器缺失 favicon 的 404，已补充 `app/icon.svg`；
- 原卷审核、逐项 T/F 编辑和 PDF 预览走管理员 API，未在普通学生界面暴露。

## 尚未在本机执行

本机未安装 Docker，因此未运行 `docker compose up`。CI 定义了 PostgreSQL 16 服务、Alembic 迁移、seed 和 API smoke；真实部署前仍需在目标环境执行容器启动与数据库备份/恢复演练。

未配置 LLM 凭据，因此未声称真实模型调用已通过；未配置时 UI 明确显示规则导师。正式题目答案、图表、共用题干和知识映射需要教研审核后才可发布。
