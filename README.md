# CFD 团队工时统计系统

Spring Boot + Vue 3 monorepo，用于同步 Jira CFD 团队工时、聚合日/周/季度统计、缓存到 Supabase，并对工时不足成员发送提醒邮件。历史 Python/Streamlit 实现已从当前分支移除。

## 项目结构

```text
cfd-management/
├── backend/                 # Spring Boot 3 / Java 17 / Maven
├── frontend/                # Vue 3 / TypeScript / Vite
├── .env.example             # 环境变量模板
├── AGENTS.md                # 仓库协作约定
└── CLAUDE.md                # 本地开发上下文说明
```

## 环境要求

- Java 17+
- Maven 3.9+
- Node.js 18+
- npm 9+

## 快速启动

`.env.example` 是配置模板。后端通过 `backend/src/main/resources/application.yml` 读取环境变量，因此本地运行前需要先把变量导入 shell 或 IDE 运行配置。

```bash
# 1. 准备环境变量
cp .env.example .env
set -a
source .env
set +a

# 2. 启动后端
cd backend
mvn spring-boot:run

# 3. 启动前端（新终端）
cd frontend
npm install
npm run dev
```

本地默认地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8080`

Vite 已配置 `/api` 代理到后端。

## 常用命令

```bash
# 后端测试
cd backend
mvn test

# 后端打包
cd backend
mvn package

# 前端构建
cd frontend
npm run build

# 前端预览构建产物
cd frontend
npm run preview
```

## 当前能力

- Jira 团队成员拉取：`GET /api/team/members`
- 工时区间汇总：`GET /api/worklog/range`
- 工时明细读取：`GET /api/worklog/entries`
- Jira 数据同步：`POST /api/sync`
- 工时提醒邮件：`POST /api/email/remind`
- 节假日查询：`GET /api/holidays`

前端当前提供：

- `/worklog`：工时范围看板、缓存读取、强制同步、提醒邮件发送
- `/bug`：Bug 页面占位视图

## 配置说明

根目录 `.env.example` 保留了当前后端所需的主要变量：

- Atlassian：`ATLASSIAN_USER_EMAIL`、`ATLASSIAN_API_TOKEN`、`ATLASSIAN_CLOUD_URL`、`CFD_TEAM_ID`、`CFD_ORG_ID`
- Supabase：`SUPABASE_URL`、`SUPABASE_ANON_KEY`
- SMTP：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`、`SMTP_SENDER`
- 业务配置：`DAILY_TARGET_HOURS`、`MEMBER_EMAIL_MAP`、`WEBUI_AUTO_SYNC_ON_QUERY`
- 调度配置：`CFD_SCHEDULER_ENABLED`、`CFD_SYNC_CRON`、`CFD_REMINDER_CRON`、`CFD_SCHEDULER_ZONE`

更多上下文见 [CLAUDE.md](CLAUDE.md) 和 [AGENTS.md](AGENTS.md)。
