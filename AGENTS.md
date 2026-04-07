# Repository Guidelines（仓库协作指南）

## 项目结构与模块组织
- `main.py`：CLI 入口，负责拉取、聚合、缓存与提醒流程编排。
- `app.py`：Streamlit Web UI 入口（`streamlit run app.py`）。
- `cfd_report/`：核心业务模块，按职责拆分：
- `atlassian.py`（Jira/Teams 拉取）、`supabase_client.py`（缓存读写）
- `aggregator.py`（日/周/季度聚合）、`reporter.py`（报告渲染）
- `emailer.py`、`holidays.py`、`config.py`（提醒、节假日、配置）
- `.env.example` 提供配置模板；`requirements.txt` 管理依赖。

## 构建、运行与开发命令
- `python -m venv .venv && source .venv/bin/activate`：创建并激活虚拟环境。
- `pip install -r requirements.txt`：安装项目依赖。
- `python main.py --no-email`：运行 CLI 报告（不发邮件）。
- `python main.py --date 2026-04-03 --week-only --no-email`：按指定日期/范围验证逻辑。
- `streamlit run app.py`：启动本地页面（默认 `http://localhost:8501`）。
- `python -m compileall .`：提交前做一次快速语法检查（可选）。

## 编码风格与命名规范
- Python 3.10+，统一 4 空格缩进；新增/修改代码建议补充类型注解。
- 命名规则：函数/变量/模块使用 `snake_case`，类使用 `PascalCase`（如 `Config`）。
- 入口层保持轻量，通用逻辑优先下沉到 `cfd_report/` 内对应模块。
- 仓库当前未配置强制格式化与 lint；请保持与现有 import 顺序和 docstring 风格一致。

## 测试指南
- 当前仓库未提交自动化测试；合并前至少执行手动冒烟：
- CLI：`python main.py --no-email`
- UI：`streamlit run app.py`，确认日/周/季度表格可正常渲染
- 新增测试建议使用 `pytest`，放在 `tests/`，文件命名为 `test_<module>.py`（示例：`test_aggregator.py`）。
- 优先覆盖日期区间计算、聚合准确性、缓存命中/未命中分支。

## 第三方 API 与外部服务
- Atlassian Teams API：`POST https://api.atlassian.com/gateway/api/public/teams/v1/org/{org_id}/teams/{team_id}/members`（获取团队成员）。
- Jira REST API v3：
- `GET {ATLASSIAN_CLOUD_URL}/rest/api/3/search`（JQL 查询 issue/worklog）
- `GET {ATLASSIAN_CLOUD_URL}/rest/api/3/user?accountId=...`
- `GET {ATLASSIAN_CLOUD_URL}/rest/api/3/issue/{issue_id}/worklog`
- Supabase REST API：`{SUPABASE_URL}/rest/v1/*`（`worklog_daily|weekly|quarterly` 的查询与 upsert）。
- Nager.Date API：`GET https://date.nager.at/api/v3/PublicHolidays/{year}/CN`（失败时回退本地节假日数据）。
- SMTP 服务：通过 `SMTP_HOST/PORT/USER/PASSWORD` 发送工时不足提醒邮件（465 使用 SSL，其他端口走 STARTTLS）。

## 提交与 PR 规范
- 当前目录不含 `.git` 历史，默认采用 Conventional Commits：`feat:`、`fix:`、`refactor:`、`docs:`。
- 单次提交聚焦一个逻辑变更，避免混入无关重构。
- PR 需说明变更目的、影响模块、配置项变化、验证命令与结果。
- 涉及 UI 时附页面截图；涉及 CLI/报告格式时附示例输出。

## 配置与安全
- 首次开发先复制 `.env.example` 为 `.env`，禁止提交任何密钥。
- 对 `ATLASSIAN_API_TOKEN`、`SUPABASE_ANON_KEY`、`SMTP_PASSWORD` 按敏感信息管理。
- `MEMBER_EMAIL_MAP` 必须是合法 JSON；上线前先做解析校验与小范围试发。
