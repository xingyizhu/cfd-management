# CFD 团队工时统计项目

## 项目概述

统计 Jira CFD 项目全体成员的每日工时，按日/周/季度维度汇总，缓存至 Supabase，并对当日工时不足 7.5h 的成员发送邮件提醒。提供 CLI 和 Streamlit Web UI 两种访问方式。

## 目录结构

```
Management/
├── CLAUDE.md               # 本文件（Claude Code 自动加载）
├── .env                    # 实际配置（不提交 git）
├── .env.example            # 环境变量模板
├── requirements.txt        # requests, streamlit, python-dotenv, pandas
├── main.py                 # CLI 入口
├── app.py                  # Streamlit Web UI（streamlit run app.py）
└── cfd_report/
    ├── config.py           # Config dataclass，从 .env 加载
    ├── atlassian.py        # Atlassian Teams API + Jira API
    ├── supabase_client.py  # Supabase 缓存读写
    ├── aggregator.py       # worklog 聚合（日/周/季度）
    ├── holidays.py         # 中国法定节假日
    ├── reporter.py         # 报告数据结构
    └── emailer.py          # SMTP 邮件发送
```

## 环境配置

复制 `.env.example` 为 `.env` 并填写：

| 变量 | 说明 |
|------|------|
| `ATLASSIAN_USER_EMAIL` | Jira 登录邮箱 |
| `ATLASSIAN_API_TOKEN` | Atlassian API Token（在 id.atlassian.com 生成）|
| `ATLASSIAN_CLOUD_URL` | Jira 实例地址 |
| `CFD_TEAM_ID` | CFD 团队 ID（固定，一般不改）|
| `CFD_ORG_ID` | Atlassian Org ID（固定，一般不改）|
| `SUPABASE_URL` | Supabase 项目 URL |
| `SUPABASE_ANON_KEY` | Supabase anon key |
| `SMTP_HOST/PORT/USER/PASSWORD` | 邮件服务器配置 |
| `DAILY_TARGET_HOURS` | 日工时目标（默认 7.5）|
| `MEMBER_EMAIL_MAP` | JSON 字符串，accountId → 邮箱 |

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# CLI：生成今日报告（不发邮件）
python main.py --no-email

# CLI：指定日期
python main.py --date 2026-04-03 --no-email

# CLI：仅查看本周数据
python main.py --week-only --no-email

# Web UI
streamlit run app.py   # 访问 http://localhost:8501
```

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

### worklog_weekly（week_start 为周一日期）
### worklog_quarterly（quarter_key 格式：2026-Q2）

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

## 关联 Skill

`/jira-cfd-daily-report` — 通过 Claude Code skill 触发完整报告流程（含 MCP 工具调用）

## 缓存策略

每次运行先查 Supabase 是否有当日数据：
- **命中** → 直接从数据库读取展示，跳过 Jira API 调用
- **未命中** → 查询 Jira → 聚合 → 写入 Supabase → 展示

## 注意事项

- Jira API 每次最多返回 20 条 worklog，超出自动分页
- `MEMBER_EMAIL_MAP` 需手动维护 accountId → 邮箱的映射
- 节假日数据优先从 nager.at API 获取，失败时使用硬编码兜底
