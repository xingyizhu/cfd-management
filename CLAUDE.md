# CFD 团队工时统计项目

## 项目概述

当前分支已切换为 Spring Boot + Vue 3 monorepo。后端负责 Jira/Supabase/SMTP 集成、工时聚合和提醒接口，前端负责区间工时看板与交互。历史 Python/Streamlit 实现已移除。

## 目录结构

```text
cfd-management/
├── CLAUDE.md
├── AGENTS.md
├── README.md
├── .env.example
├── backend/
│   ├── pom.xml
│   └── src/
│       ├── main/java/com/cfd/
│       │   ├── config/      # AppProperties、CORS、RestTemplate
│       │   ├── controller/  # REST API 入口
│       │   ├── service/     # 聚合、同步、提醒、节假日
│       │   ├── client/      # Atlassian / Supabase HTTP 客户端
│       │   └── model/       # DTO
│       ├── main/resources/application.yml
│       └── test/java/com/cfd/service/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── api/             # axios API 封装
        ├── components/      # 通用组件
        ├── router/          # Vue Router
        ├── stores/          # Pinia store
        ├── types/           # TypeScript 类型
        └── views/           # 页面视图
```

## 环境配置

`.env.example` 仍是统一模板，但后端不会自动读取根目录 `.env` 文件；运行前需要把变量导入当前 shell 或 IDE。

```bash
cp .env.example .env
set -a
source .env
set +a
```

关键变量：

| 变量 | 说明 |
|------|------|
| `ATLASSIAN_USER_EMAIL` | Jira 登录邮箱 |
| `ATLASSIAN_API_TOKEN` | Atlassian API Token |
| `ATLASSIAN_CLOUD_URL` | Jira 实例地址 |
| `CFD_TEAM_ID` / `CFD_ORG_ID` | 团队和组织标识 |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | Supabase 访问配置 |
| `SMTP_HOST/PORT/USER/PASSWORD/SENDER` | 邮件服务器配置 |
| `DAILY_TARGET_HOURS` | 日工时目标 |
| `MEMBER_EMAIL_MAP` | accountId 到邮箱的 JSON 映射 |
| `CFD_SCHEDULER_ENABLED` / `CFD_SYNC_CRON` / `CFD_REMINDER_CRON` / `CFD_SCHEDULER_ZONE` | 定时任务配置 |

## 常用命令

```bash
# 启动后端
cd backend
mvn spring-boot:run

# 后端测试与打包
cd backend
mvn test
mvn package

# 启动前端
cd frontend
npm install
npm run dev

# 前端构建
cd frontend
npm run build
```

默认端口：

- 后端：`http://localhost:8080`
- 前端：`http://localhost:5173`

## 当前 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/team/members` | 获取团队成员 |
| `GET` | `/api/worklog/range` | 获取区间汇总 |
| `GET` | `/api/worklog/entries` | 获取区间明细 |
| `POST` | `/api/sync` | 同步 Jira 数据到 Supabase |
| `POST` | `/api/email/remind` | 发送工时提醒邮件 |
| `GET` | `/api/holidays` | 查询节假日和工作日 |
| `GET` | `/api/reports/daily` | 读取日聚合 |
| `GET` | `/api/reports/weekly` | 读取周聚合 |
| `GET` | `/api/reports/quarterly` | 读取季度聚合 |

## Supabase 表结构

### worklog_daily
| 字段 | 类型 | 说明 |
|------|------|------|
| account_id | text (PK) | Jira accountId |
| work_date | date (PK) | 工作日期 |
| display_name | text | 显示名称 |
| logged_sec | int | 已记录秒数 |
| estimated_sec | int | 原始预估秒数 |
| issue_count | int | Issue 数量 |
| issue_keys | text[] | Issue Key 列表 |
| updated_at | timestamptz | 更新时间 |

### worklog_weekly

`week_start` 为周一起始日期。

### worklog_quarterly

`quarter_key` 格式为 `2026-Q2`。

### worklog_entries
| 字段 | 类型 | 说明 |
|------|------|------|
| account_id | text (PK) | Jira accountId |
| work_date | date (PK) | 工作日期 |
| issue_key | text (PK) | Jira Issue Key |
| display_name | text | 成员显示名 |
| issue_summary | text | Issue 摘要 |
| time_sec | int | 该成员在该日该事项登记的秒数 |
| estimated_sec | int | Issue 原始预估秒数 |
| project_key | text | Jira 项目 Key |
| project_name | text | Jira 项目名称 |
| status_name | text | Jira 当前状态名称 |
| updated_at | timestamptz | 更新时间 |

## 开发注意事项

- Vite 已代理 `/api` 到 `http://localhost:8080`。
- Jira worklog 拉取需要处理分页，节假日优先使用 Nager.Date，失败时走本地兜底。
- `MEMBER_EMAIL_MAP` 仍需手动维护，发送邮件前先确认账号映射完整。
- 对外配置应优先通过环境变量注入，不要把真实密钥写入源码默认值。
