# 重构计划：Spring Boot + Vue 3 Monorepo

## Context

当前项目是 CFD 团队工时统计系统，现有技术栈为 Python (Streamlit + requests)。
重构目标：将后端迁移至 Spring Boot + Maven，前端迁移至 Vue 3 + TypeScript，保持 Monorepo 结构，数据库继续使用 Supabase。

---

## 现有系统分析

**核心功能模块（需全部迁移）：**
1. **Jira 数据同步**：调用 Atlassian Teams API + Jira REST API，拉取指定成员的 worklog 数据
2. **数据聚合**：按日/周/季度维度聚合工时，识别工时不足成员
3. **Supabase 缓存**：读写 `worklog_daily`、`worklog_weekly`、`worklog_quarterly`、`worklog_entries` 四张表
4. **Web UI**：工时范围看板、任务估时看板、成员任务归纳、工时不足提醒
5. **邮件提醒**：对工时不足成员发送 SMTP 邮件
6. **AI 摘要**：调用 OpenAI API 生成成员任务汇报话术（可选）
7. **节假日判断**：中国法定节假日检查

**配置项（需迁移到 application.yml）：**
- Atlassian: user_email, api_token, cloud_url, team_id, org_id
- Supabase: url, anon_key
- OpenAI: api_key, base_url, model
- SMTP: host, port, user, password, sender
- Business: daily_target_hours, member_email_map, webui_auto_sync_on_query

---

## 目标架构

```
cfd-management/              ← 保留现有 Git 根目录
├── backend/                 ← Spring Boot Maven 项目（新建）
│   ├── pom.xml
│   └── src/main/java/com/cfd/
│       ├── CfdApplication.java
│       ├── config/          ← AppProperties, WebConfig (CORS)
│       ├── controller/      ← REST 控制器
│       ├── service/         ← 业务逻辑（对应 Python 模块）
│       ├── model/           ← DTO / 实体类
│       └── client/          ← Atlassian / Supabase / OpenAI HTTP 客户端
├── frontend/                ← Vue 3 + TypeScript 项目（新建）
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── api/             ← axios 封装，对接后端 REST API
│       ├── stores/          ← Pinia 状态管理
│       ├── views/           ← 页面：工时看板、任务估时看板等
│       ├── components/      ← 通用组件
│       └── types/           ← TypeScript 类型定义
├── .env.example             ← 保留（后端 application.yml 读同一套环境变量）
└── (原 Python 文件暂保留，待前后端验证通过后删除)
```

---

## 实现步骤

### Phase 0：准备工作

1. 切换新分支：`git checkout -b refactor/spring-boot-vue3` ✅
2. 将本计划文件保存到仓库：`REFACTOR_PLAN.md`（根目录）✅

### Phase 1：Monorepo 骨架搭建

1. 在根目录创建 `backend/` 子目录，手动创建 Spring Boot Maven 项目结构
   - 依赖：`spring-boot-starter-web`、`spring-boot-starter-mail`、`spring-boot-configuration-processor`、`lombok`
   - Java 17，Spring Boot 3.x
2. 在根目录创建 `frontend/` 子目录，创建 Vue 3 + TypeScript + Pinia + Vue Router + Vite 项目
3. 根目录更新 `.gitignore`（排除 `backend/target/`、`frontend/node_modules/`、`frontend/dist/`）

### Phase 2：后端 Spring Boot

#### 2.1 配置层
- `AppProperties.java`：`@ConfigurationProperties(prefix = "cfd")` 映射所有配置项
- `application.yml`：读取环境变量（`${ATLASSIAN_USER_EMAIL}` 等），与现有 `.env` 保持一致

#### 2.2 HTTP 客户端（对应 `atlassian.py` + `supabase_client.py`）
- `AtlassianClient.java`：封装 Jira Teams API 和 JQL 搜索
  - `getTeamMembers()` → `atlassian.py:get_team_members()`
  - `searchIssues()` → `atlassian.py:search_jira_issues()`
  - `fetchAllWorklogs()` → `atlassian.py:_fetch_all_worklogs()`
- `SupabaseClient.java`：封装 Supabase PostgREST REST API（继续用 HTTP 而非 JDBC）
  - 读写 `worklog_daily`、`worklog_weekly`、`worklog_quarterly`、`worklog_entries`

#### 2.3 业务服务层（对应 `aggregator.py` + `sync.py` + `reporter.py`）
- `AggregatorService.java`：工时聚合逻辑（日/周/季度），find_under_logged_range
- `SyncService.java`：Jira → Supabase 同步
- `HolidayService.java`：中国节假日判断，内置节假日数据
- `EmailService.java`：SMTP 邮件发送
- `AiSummaryService.java`：OpenAI API 调用生成 AI 摘要（可选）

#### 2.4 REST 控制器

| Endpoint | 方法 | 说明 |
|---|---|---|
| `/api/team/members` | GET | 获取团队成员列表 |
| `/api/worklog/range` | GET | 按日期范围聚合工时 |
| `/api/worklog/entries` | GET | 按日期范围获取 entries |
| `/api/sync` | POST | 触发 Jira → Supabase 同步 |
| `/api/email/remind` | POST | 发送工时不足提醒邮件 |
| `/api/holidays` | GET | 查询节假日 |
| `/api/ai/summary` | POST | 生成 AI 汇报话术（可选） |

#### 2.5 DTO 设计
- `TeamMemberDto`：accountId, displayName, emailAddress, active
- `WorklogRangeRowDto`：accountId, displayName, loggedSec, estimatedSec, issueCount
- `WorklogEntryDto`：accountId, displayName, workDate, issueKey, issueSummary, timeSec, estimatedSec, projectKey, projectName, statusName
- `RangeSummaryDto`：meta(dateFrom, dateTo, workdayCount), rangeRows, underLogged
- `SyncResultDto`：entries, daily, weekly, quarterly counts

### Phase 3：前端 Vue 3

#### 3.1 API 层（`src/api/`）
- `worklogApi.ts`：对接所有后端 REST 接口，axios 封装
- `types.ts`：对应后端 DTO 的 TypeScript 接口定义

#### 3.2 State（`src/stores/`）
- `useWorklogStore.ts`：存储当前日期范围、worklog 数据、团队成员列表
- `useConfigStore.ts`：存储 UI 配置（sync 策略、日工时目标等）

#### 3.3 Views（对应 Streamlit 页面模块）
- `WorklogDashboard.vue`：工时范围看板（metrics + 汇总表 + 柱状图）
- `EstimateBoardView.vue`：任务估时看板（无预估 / 高预估）
- `MemberTaskView.vue`：成员任务归纳卡片
- `UnderLoggedView.vue`：工时不足提醒
- `BugView.vue`：Bug 统计占位页

#### 3.4 组件（`src/components/`）
- `MetricCard.vue`：指标卡片
- `CfdTable.vue`：通用表格（带 issue 链接跳转）
- `MemberCard.vue`：成员任务卡片
- `DateRangePicker.vue`：日期范围选择 + 快捷按钮（当周/当季度）

#### 3.5 样式
- 延续现有深蓝色主题（CSS 变量）
- 使用 Noto Sans SC + Noto Serif SC 字体

### Phase 4：集成联调

1. 后端启动在 `:8080`，前端 Vite dev 在 `:5173`，配置 CORS 允许跨域
2. 联调所有 API 接口
3. 生产构建：`mvn package` 打 JAR，`npm run build` 打 dist

---

## 关键文件映射

| 新文件 | 对应现有 Python 模块 |
|---|---|
| `backend/src/.../client/AtlassianClient.java` | `cfd_report/atlassian.py` |
| `backend/src/.../client/SupabaseClient.java` | `cfd_report/supabase_client.py` |
| `backend/src/.../service/AggregatorService.java` | `cfd_report/aggregator.py` |
| `backend/src/.../service/SyncService.java` | `cfd_report/sync.py` |
| `backend/src/.../service/HolidayService.java` | `cfd_report/holidays.py` |
| `backend/src/.../service/EmailService.java` | `cfd_report/emailer.py` |
| `backend/src/.../config/AppProperties.java` | `cfd_report/config.py` |
| `frontend/src/views/WorklogDashboard.vue` | `app.py`（工时看板部分） |
| `frontend/src/views/EstimateBoardView.vue` | `app.py`（估时看板部分） |

---

## 验证方法

1. **后端接口测试**：curl/Postman 调用各 REST 接口，验证返回数据结构
2. **端到端验证**：
   - 前端选择日期范围 → 触发 `/api/sync` → 刷新 `/api/worklog/range` → 检查 metrics 数据
   - 触发邮件发送 → 确认收件箱收到提醒
3. **与 Supabase 验证**：Supabase 表数据在 Spring Boot 写入后与 Python 版本写入结果一致

---

## 分阶段交付

- **里程碑 1**：后端 + Supabase 读写可用（所有 API 接口联通）
- **里程碑 2**：前端基础看板页面可用（工时范围看板）
- **里程碑 3**：前端完整页面 + 邮件 + AI 摘要功能
- **里程碑 4**：Python 旧代码移除，单 JAR 部署
