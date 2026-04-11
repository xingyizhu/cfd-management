# Repository Guidelines（仓库协作指南）

## 项目结构与模块组织
- `backend/`：Spring Boot 后端，按 `config`、`controller`、`service`、`client`、`model` 分层。
- `frontend/`：Vue 3 前端，主要包含 `api`、`components`、`router`、`stores`、`types`、`views`。
- `.env.example`：根目录环境变量模板；后端通过 `application.yml` 映射这些变量。
- `README.md`、`CLAUDE.md`、`AGENTS.md`：分别维护项目说明、开发上下文和协作约定。

## 构建、运行与开发命令
- `cp .env.example .env && set -a && source .env && set +a`：准备并导入环境变量。
- `cd backend && mvn spring-boot:run`：启动 Spring Boot 后端，默认端口 `8080`。
- `cd backend && mvn test`：运行后端测试。
- `cd backend && mvn package`：打包后端 JAR。
- `cd frontend && npm install`：安装前端依赖。
- `cd frontend && npm run dev`：启动 Vite 开发服务器，默认端口 `5173`。
- `cd frontend && npm run build`：构建前端生产包。

## 编码风格与命名规范
- 后端使用 Java 17，保持 Spring Boot 分层清晰，控制器仅负责入参和响应组装，业务逻辑下沉到 `service`。
- Java 命名：类使用 `PascalCase`，方法和字段使用 `camelCase`，常量使用 `UPPER_SNAKE_CASE`。
- 前端使用 Vue 3 + TypeScript；组件文件采用 `PascalCase.vue`，store 和工具模块采用 `camelCase`/`kebab-case` 与现有风格一致。
- 修改现有代码时保持 import 顺序、DTO 命名、接口字段风格一致；前后端交互字段优先与现有 API 对齐。

## 测试指南
- 合并前至少执行：
- 后端：`cd backend && mvn test`
- 前端：`cd frontend && npm run build`
- 手动冒烟：启动前后端后访问 `http://localhost:5173/worklog`，确认区间汇总、同步按钮和提醒邮件入口可正常工作。
- 新增后端测试放在 `backend/src/test/java/...`，优先覆盖日期区间、聚合逻辑、节假日判断和 Supabase 映射。

## 第三方 API 与外部服务
- Atlassian Teams API：`POST https://api.atlassian.com/gateway/api/public/teams/v1/org/{org_id}/teams/{team_id}/members`
- Jira REST API v3：
- `GET {ATLASSIAN_CLOUD_URL}/rest/api/3/search`
- `GET {ATLASSIAN_CLOUD_URL}/rest/api/3/user?accountId=...`
- `GET {ATLASSIAN_CLOUD_URL}/rest/api/3/issue/{issue_id}/worklog`
- Supabase REST API：`{SUPABASE_URL}/rest/v1/*`
- Nager.Date API：`GET https://date.nager.at/api/v3/PublicHolidays/{year}/CN`
- SMTP：通过 `SMTP_HOST/PORT/USER/PASSWORD` 发送提醒邮件；465 端口走 SSL。

## 提交与 PR 规范
- 采用 Conventional Commits：`feat:`、`fix:`、`refactor:`、`docs:`、`chore:`。
- 单次提交聚焦一个明确主题，不混入无关格式化或生成文件。
- PR 需说明变更目的、影响范围、配置变化、验证命令与结果。
- 涉及接口调整时附请求示例；涉及 UI 时附页面截图。

## 配置与安全
- `.env` 仅用于本地开发参考，真实运行时需将变量导入 shell、IDE 或部署环境，禁止提交任何密钥。
- 严禁在源码默认值中保留真实 `ATLASSIAN_API_TOKEN`、`SUPABASE_ANON_KEY`、`SMTP_PASSWORD` 等敏感信息。
- `MEMBER_EMAIL_MAP` 必须是合法 JSON；改动邮件提醒逻辑前先用小范围账号验证。
